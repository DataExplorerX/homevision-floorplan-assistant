# HomeVision — AI Floor Plan Assistant

**Live demo: http://13.234.217.141:8000**

A chat-driven floor plan search tool: describe what you want ("a 2 bedroom
apartment with a balcony") and get back real, matching floor plans from the
[CubiCasa5K](https://github.com/CubiCasa/CubiCasa5k) dataset, using hybrid
search (exact bedroom-count filtering + semantic similarity ranking).

## Status

- ✅ **Data pipeline** (download → parse → caption → embed → ingest): working
- ✅ **Hybrid search** (structured filter + semantic ranking): working
- ✅ **FastAPI backend + chat UI**: working
- ✅ **Deployed**: running live on an AWS EC2 instance (see "Deployment" below)

## Why this dataset, and a licensing note

CubiCasa5K is licensed **CC BY-NC-SA 4.0** (non-commercial, attribution
required, share-alike) — fine for this personal/portfolio project, but if
this is ever extended commercially, the dataset would need to be swapped
for something with a commercial-use license.

## Architecture

```
CubiCasa5K (remote, on Zenodo)
      │  partial download via HTTP range requests (remotezip)
      ▼
data_pipeline/01_download_subset.py   -- pulls a 60-sample subset, prioritizing
                                          the high_quality_architectural
                                          subset (proper room labels,
                                          unlike the "colorful" subset
                                          which is mostly "Undefined")
      ▼
data_pipeline/02_parse_floorplans.py  -- parses each model.svg, extracts
                                          room types from <g class="Space
                                          ..."> elements, derives an
                                          authoritative BHK label by
                                          counting "Bedroom" rooms, and
                                          excludes likely multi-unit floor
                                          plans (see bugs section below) --
                                          59 samples make it through
      ▼
data_pipeline/03_polish_captions.py   -- rewrites the room list into a
                                          natural sentence via Groq
                                          (free tier). Bedroom count is
                                          PREPENDED from our own parsed
                                          data, never restated by the LLM,
                                          so it can never be wrong.
      ▼
data_pipeline/04_audit_captions.py    -- verifies no caption contradicts
                                          its authoritative BHK label
      ▼
data_pipeline/05_setup_supabase_table.sql  -- creates the pgvector-enabled
                                               table (run once, in Supabase's
                                               SQL Editor)
      ▼
data_pipeline/06_ingest_to_supabase.py -- embeds each caption locally
                                           (sentence-transformers,
                                           no API needed) and upserts
                                           everything into Supabase
      ▼
search/hybrid_search.py               -- the actual product logic:
                                          search/query_parser.py splits a
                                          user's message into an exact BHK
                                          filter + a semantic query, then
                                          hybrid_search.py applies the
                                          filter in SQL and ranks by vector
                                          similarity within that filtered set
```

## Why hybrid search, not just semantic search

Early testing showed pure semantic search failing in an important way: for
"a 2 bedroom apartment with a balcony," a **Studio** ranked above actual
2BHK results, because the embedding model treats "2 bedroom" as a soft
signal, not a hard requirement. The fix: use Groq to extract the bedroom
count as a **structured SQL filter** (exact, can't be wrong), and only use
semantic ranking for the genuinely fuzzy part of the request (balcony,
style, layout feel).

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You'll need two free API credentials, set as environment variables in your
notebook/shell before running anything (never commit these, never paste
them into chat):

```python
import os
os.environ["GROQ_API_KEY"] = "..."       # free, no card: console.groq.com/keys
os.environ["SUPABASE_DB_URL"] = "..."    # from Supabase: Settings -> Database
```

## Running the pipeline, in order

All commands assume you're running from this project's root folder (so
relative paths like `cubicasa5k_subset_v2/` and `parsed_floorplans.json`
land here, not inside `data_pipeline/`).

```bash
python data_pipeline/01_download_subset.py     # ~1-2 min, downloads a subset only
python data_pipeline/02_parse_floorplans.py    # instant, parses room data
python data_pipeline/03_polish_captions.py     # ~3 min, Groq API calls, resumable
python data_pipeline/04_audit_captions.py      # instant, should report 0 mismatches
# Run 05_setup_supabase_table.sql manually in Supabase's SQL Editor (one-time)
python data_pipeline/06_ingest_to_supabase.py  # ~1 min, embeds + upserts to DB
```

## Testing the search

```bash
python tools/test_semantic_search.py   # pure semantic search (shows the limitation)
python search/hybrid_search.py         # full hybrid search (the real thing)
```

## Running the full app (API + chat UI)

The live version is already running at **http://13.234.217.141:8000** — no setup needed to just try it.

To run it yourself, locally:

```bash
uvicorn api.app:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser — a simple chat interface where you can type a request ("a 2 bedroom apartment with a balcony") and see matching floor plan images with their captions.

The API also has interactive docs at **http://localhost:8000/docs** (FastAPI's built-in Swagger UI) — useful for testing `POST /api/search` directly without the frontend.

## Deployment

Running on a free-tier AWS EC2 instance (Ubuntu, t2/t3.micro), not Lambda —
deliberately a different AWS service than the AWS Ops MCP Server project,
both for a genuine technical reason (this app's `sentence-transformers`/
`torch` dependency is large and doesn't fit Lambda's deployment model
without adding container-image complexity) and because showing both
serverless and traditional-VM deployment experience is a stronger signal
than repeating the same pattern twice.

The app runs as a systemd service (`homevision.service`) so it survives
SSH disconnects and restarts automatically if it ever crashes. The floor
plan image files are downloaded directly onto the EC2 instance via
`01_download_subset.py` -- they're not committed to the repo, both because
of the dataset's non-commercial license and because they're regeneratable
data, not code.

## Utility / troubleshooting scripts (`tools/`)

- `inspect_svg.py` — dump a single `model.svg`'s structure; useful if
  CubiCasa5k's format ever looks different than expected
- `diagnose_supabase.py` — checks row counts, null embeddings, and runs the
  raw vector-search query with full error output
- `diagnose_captions.py` — lists exactly which sample IDs have/don't have a
  polished caption
- `audit_multiunit.py` — flags samples likely representing a multi-unit
  building floor rather than a single dwelling (detected via duplicate
  exact "Kitchen" rooms, a signal a genuine single dwelling doesn't have)
- `data_pipeline/reset_captions_utility.py` — clears `caption_polished` for
  the first N samples in `parsed_floorplans_polished.json`, forcing them to
  regenerate on the next run of `03_polish_captions.py`. Edit `NUM_TO_RESET`
  at the top of the file.

## Extending it (next steps)

- Consider re-adding an IVFFLAT/HNSW index once the dataset grows well
  beyond ~1,000 rows (removed for now — at only 59 rows it was actually
  *breaking* search results by approximating over too few clusters)
