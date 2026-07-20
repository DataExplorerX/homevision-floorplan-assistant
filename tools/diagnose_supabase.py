import os
import traceback

import psycopg2

DB_URL = os.environ["SUPABASE_DB_URL"]

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("=== Row count ===")
cur.execute("select count(*) from floorplans;")
print(cur.fetchone())

print("\n=== Sample of 3 rows (no vector search, just plain SELECT) ===")
cur.execute("select sample_id, bhk_label, caption from floorplans limit 3;")
for row in cur.fetchall():
    print(row)

print("\n=== Check embedding column isn't null ===")
cur.execute("select count(*) from floorplans where embedding is null;")
print("rows with NULL embedding:", cur.fetchone())

print("\n=== Try the actual vector search query, with full error output if it fails ===")
try:
    test_embedding = [0.0] * 384  # dummy vector just to test the query mechanics
    cur.execute(
        """
        select sample_id, bhk_label, caption, embedding <=> %s::vector as distance
        from floorplans
        order by distance asc
        limit 3
        """,
        (test_embedding,),
    )
    rows = cur.fetchall()
    print(f"Query succeeded. Row count returned: {len(rows)}")
    for row in rows:
        print(row)
except Exception:
    print("ERROR during vector search (full traceback below):")
    print(traceback.format_exc())

conn.close()
