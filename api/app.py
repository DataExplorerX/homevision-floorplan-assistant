"""
FastAPI backend for HomeVision.

Wraps search/hybrid_search.py in a single POST endpoint, and serves the
floor plan images (from the locally-downloaded CubiCasa5k subset) as static
files so the frontend can actually display them.

Run locally with:
    uvicorn api.app:app --reload --port 8000

Requires the same environment variables as the rest of the pipeline:
    GROQ_API_KEY, SUPABASE_DB_URL
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Make the sibling "search" package importable regardless of where uvicorn
# is launched from. hybrid_search.py internally does a plain
# "from query_parser import parse_query" (not a package-relative import),
# so the search/ folder itself needs to be on sys.path too, not just the
# project root -- otherwise that internal import fails.
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "search"))
from search.hybrid_search import search as run_hybrid_search  # noqa: E402

app = FastAPI(title="HomeVision API")

# Permissive CORS for local development -- the frontend (served from the
# same origin here) doesn't strictly need this, but it keeps things simple
# if you ever serve the frontend from a different port/origin later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the actual floor plan images directly from the downloaded dataset
# folder, so the frontend can reference them by URL instead of needing
# base64-encoded blobs in the JSON response.
IMAGES_ROOT = Path(__file__).parent.parent / "cubicasa5k_subset_v2"
if IMAGES_ROOT.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_ROOT)), name="images")

# Serve the frontend's static files (index.html, etc.)
STATIC_ROOT = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")


class SearchRequest(BaseModel):
    message: str


class SearchResultItem(BaseModel):
    sample_id: str
    bhk_label: str
    caption: str
    image_url: str
    distance: float


class SearchResponse(BaseModel):
    parsed_intent: dict
    results: list[SearchResultItem]


@app.get("/")
def index():
    """Serve the chat UI's HTML file at the root."""
    from fastapi.responses import FileResponse
    return FileResponse(str(STATIC_ROOT / "index.html"))


@app.post("/api/search", response_model=SearchResponse)
def search_endpoint(req: SearchRequest):
    results, parsed = run_hybrid_search(req.message)

    items = []
    for sample_id, bhk_label, caption, image_path, distance in results:
        # image_path looks like:
        #   cubicasa5k_subset_v2/cubicasa5k/high_quality_architectural/10096/F1_scaled.png
        # Strip the leading "cubicasa5k_subset_v2/" since that's the mount
        # point itself, to get the path relative to the static mount.
        relative_path = str(Path(image_path)).split("cubicasa5k_subset_v2/", 1)[-1]
        items.append(
            SearchResultItem(
                sample_id=sample_id,
                bhk_label=bhk_label,
                caption=caption,
                image_url=f"/images/{relative_path}",
                distance=float(distance),
            )
        )

    return SearchResponse(parsed_intent=parsed, results=items)
