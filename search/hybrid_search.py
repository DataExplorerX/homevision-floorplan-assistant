"""
Hybrid search: applies bhk_filter as an exact SQL WHERE clause (a hard
fact embeddings shouldn't be trusted to enforce), then ranks the results
within that filtered set by semantic similarity to semantic_query.

If bhk_filter is None (user didn't specify a bedroom count), falls back to
pure semantic search across everything.
"""
import os

import psycopg2
from sentence_transformers import SentenceTransformer

from query_parser import parse_query
from groq import Groq

DB_URL = os.environ["SUPABASE_DB_URL"]

print("Loading embedding model...")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def hybrid_search(conn, bhk_filter: str | None, semantic_query: str, top_k: int = 3):
    query_embedding = embed_model.encode(semantic_query).tolist()
    cur = conn.cursor()

    if bhk_filter is None:
        cur.execute(
            """
            select sample_id, bhk_label, caption, image_path,
                   embedding <=> %s::vector as distance
            from floorplans
            order by distance asc
            limit %s
            """,
            (query_embedding, top_k),
        )
    else:
        # Studio rows store a longer descriptive bhk_label, everything else
        # is an exact "1BHK"/"2BHK"/etc. string -- LIKE with a wildcard
        # covers both cases correctly in one query.
        pattern = f"{bhk_filter}%"
        cur.execute(
            """
            select sample_id, bhk_label, caption, image_path,
                   embedding <=> %s::vector as distance
            from floorplans
            where bhk_label like %s
            order by distance asc
            limit %s
            """,
            (query_embedding, pattern, top_k),
        )

    return cur.fetchall()


def search(user_message: str, top_k: int = 3):
    """End-to-end: parse the user's message, then run the hybrid search."""
    groq_client = Groq()
    parsed = parse_query(groq_client, user_message)
    print(f"Parsed intent: {parsed}")

    conn = psycopg2.connect(DB_URL)
    results = hybrid_search(conn, parsed["bhk_filter"], parsed["semantic_query"], top_k)
    conn.close()
    return results, parsed


if __name__ == "__main__":
    test_messages = [
        "show me a 2 bedroom apartment with a balcony",
        "I want a small studio with just one bathroom",
        "a big house with 4 bedrooms and a garage",
        "something with a nice open kitchen",
    ]
    for msg in test_messages:
        print(f"\n=== \"{msg}\" ===")
        results, parsed = search(msg)
        for sample_id, bhk_label, caption, image_path, distance in results:
            print(f"  [{distance:.3f}] {sample_id} ({bhk_label}): {caption}")
