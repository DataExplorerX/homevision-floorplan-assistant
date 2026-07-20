"""
Generates a local embedding for each floor plan's polished caption, then
inserts everything (image path, room list, BHK label, caption, embedding)
into the Supabase Postgres table.

Requires:
    pip install sentence-transformers psycopg2-binary

    Set your Supabase connection string as an environment variable first:
        export SUPABASE_DB_URL="postgresql://postgres:[password]@....supabase.co:5432/postgres"

Usage:
    python ingest_to_supabase.py
"""
import json
import os

import psycopg2
from sentence_transformers import SentenceTransformer

INPUT_JSON = "parsed_floorplans_polished.json"
DB_URL = os.environ["SUPABASE_DB_URL"]

print("Loading embedding model (first run downloads ~90MB, cached after that)...")
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, small, fast, runs fine on CPU


def main():
    with open(INPUT_JSON) as f:
        samples = json.load(f)

    print(f"Generating embeddings for {len(samples)} captions...")
    captions = [s["caption_polished"] for s in samples]
    embeddings = model.encode(captions, show_progress_bar=True)

    print("Connecting to Supabase...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    inserted = 0
    for sample, embedding in zip(samples, embeddings):
        cur.execute(
            """
            insert into floorplans (sample_id, image_path, bhk_label, rooms, caption, embedding)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (sample_id) do update set
                image_path = excluded.image_path,
                bhk_label = excluded.bhk_label,
                rooms = excluded.rooms,
                caption = excluded.caption,
                embedding = excluded.embedding
            """,
            (
                sample["sample_id"],
                sample["image_path"],
                sample["bhk_label"],
                json.dumps(sample["rooms"]),
                sample["caption_polished"],
                embedding.tolist(),
            ),
        )
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone. Inserted/updated {inserted} rows in Supabase.")


if __name__ == "__main__":
    main()
