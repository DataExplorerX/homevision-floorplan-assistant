"""
Sanity-check semantic search directly against Supabase, before we build any
API or UI on top of it. Embeds a test query the same way we embedded the
captions, then asks Postgres/pgvector for the closest matches by cosine
distance.

Usage:
    python test_semantic_search.py
"""
import os

import psycopg2
from sentence_transformers import SentenceTransformer

DB_URL = os.environ["SUPABASE_DB_URL"]
TEST_QUERIES = [
    "a 2 bedroom apartment with a balcony",
    "a small studio with just one bathroom",
    "a big house with 4 bedrooms and a garage",
]

model = SentenceTransformer("all-MiniLM-L6-v2")


def search(conn, query: str, top_k: int = 3):
    embedding = model.encode(query).tolist()
    cur = conn.cursor()
    cur.execute(
        """
        select sample_id, bhk_label, caption, embedding <=> %s::vector as distance
        from floorplans
        order by distance asc
        limit %s
        """,
        (embedding, top_k),
    )
    return cur.fetchall()


def main():
    conn = psycopg2.connect(DB_URL)

    for query in TEST_QUERIES:
        print(f"\nQuery: \"{query}\"")
        results = search(conn, query)
        for sample_id, bhk_label, caption, distance in results:
            print(f"  [{distance:.3f}] {sample_id} ({bhk_label}): {caption}")

    conn.close()


if __name__ == "__main__":
    main()
