-- Mining AI Analyst — initial schema
-- Run this in the Supabase SQL editor after creating the project.

create extension if not exists vector;

-- Companies being tracked (e.g. "First Mining Gold")
create table companies (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    base_url text,
    created_at timestamptz not null default now()
);

-- PDFs/filings fetched for a company. storage_path is null unless the file
-- is persisted in Supabase Storage (left optional per the cloud-storage decision).
create table documents (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    company_id uuid not null references companies(id) on delete cascade,
    label text not null,
    source_url text not null,
    storage_path text,
    fetched_at timestamptz not null default now()
);

-- Per-user agent memory: every summary, claim-check, or analysis the agent
-- produces, so it can be recalled in later conversations.
create table agent_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    document_id uuid references documents(id) on delete set null,
    kind text not null, -- 'exec_bio_summary' | 'claim_verification' | 'peer_comparison' | 'chat'
    content text not null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

-- Shared RAG knowledge base (glossary, NI 43-101 standards, peer comps, red flags).
-- Not user-specific — same content backs every user's agent.
-- embedding dimension must match whatever embedding model you call (e.g. Voyage AI) — adjust before first insert.
create table knowledge_base (
    id uuid primary key default gen_random_uuid(),
    category text not null, -- 'glossary' | 'standard' | 'peer_comp' | 'red_flag'
    title text not null,
    content text not null,
    embedding vector(1024),
    created_at timestamptz not null default now()
);

create index on knowledge_base using ivfflat (embedding vector_cosine_ops);

-- Row Level Security: users only see their own documents/history.
alter table documents enable row level security;
alter table agent_history enable row level security;

create policy "Users manage their own documents"
    on documents for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "Users manage their own history"
    on agent_history for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- companies and knowledge_base are shared reference data: readable by any
-- logged-in user, writable only via the service role (backend, which
-- bypasses RLS entirely) — so RLS is on here too, just with a read-only policy.
alter table companies enable row level security;
alter table knowledge_base enable row level security;

create policy "Authenticated users can read companies"
    on companies for select
    using (auth.role() = 'authenticated');

create policy "Authenticated users can read knowledge_base"
    on knowledge_base for select
    using (auth.role() = 'authenticated');
