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

-- Speeds up similarity search once the table has more rows. Harmless (just
-- a bit unnecessary) at only 60 rows, but correct to set up now since it's
-- the same index you'd want in production.
create index if not exists floorplans_embedding_idx
    on floorplans
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 10);
