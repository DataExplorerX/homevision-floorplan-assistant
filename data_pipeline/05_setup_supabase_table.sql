-- Run this in Supabase's SQL Editor (Project -> SQL Editor -> New query)

-- Enables the pgvector extension, which adds a native vector type and
-- similarity-search operators to Postgres.
create extension if not exists vector;

create table if not exists floorplans (
    id bigserial primary key,
    sample_id text not null unique,
    image_path text not null,
    bhk_label text not null,
    rooms jsonb not null,
    caption text not null,
    -- all-MiniLM-L6-v2 (the embedding model we're using) produces
    -- 384-dimensional vectors -- this must match exactly or inserts will fail.
    embedding vector(384)
);

-- Deliberately NOT creating an IVFFLAT/HNSW index here. At this dataset's
-- scale (~60 rows), an approximate index actively breaks search results:
-- IVFFLAT only probes a small fraction of its clusters by default, and
-- combined with a WHERE filter (e.g. bhk_label = '2BHK') that narrows an
-- already-tiny table further, the probed cluster often has zero overlap
-- with the rows that actually match -- silently returning 0 results for
-- queries that should have real matches. A plain sequential scan (the
-- default with no index) is both exact and effectively instant at this
-- size. Only add an approximate index back once the dataset grows well
-- beyond ~1,000 rows, where the tradeoff actually starts to pay off.