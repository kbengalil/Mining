# Mining AI Analyst — Project Summary

## What It Is
A web app and AI agent for junior mining stock analysis. Users can fetch investor documents from a company's IR pages, download them, and chat with an AI analyst about the company — its financials, management team, red flags, and more.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI (Python) | Handles scraping, AI calls, file downloads |
| Database | Supabase (Postgres) | User data, summaries, RAG knowledge base |
| Vector search | Supabase pgvector | For RAG similarity search (not yet built) |
| AI / Chat | Gemini 2.5 Flash | Via raw REST API (google-genai SDK had auth issues) |
| Frontend | Next.js (React) | Decided — not yet built. Client-side rendering only (no SSR for now — SSR + auth deferred until multi-user launch) |
| Current test UI | Plain HTML | Temporary, will be replaced by Next.js |
| Hosting | TBD | Render/Fly.io for backend, Vercel for frontend |

---

## What's Been Built

### 1. Supabase Schema (`supabase/schema.sql`)
Four tables:
- `companies` — mining companies tracked
- `documents` — PDFs fetched per user
- `agent_history` — per-user AI analysis history (the agent's "memory")
- `knowledge_base` — shared RAG content with pgvector embeddings

Row Level Security enabled on all tables.

### 2. FastAPI Backend (`backend/`)

**Scraping** (`scraping.py`)
- Scrapes investor-relations pages for PDF links using `requests` + BeautifulSoup
- Browser-like User-Agent header (site blocks plain Python requests)
- Per-page error reporting (blocked, timeout, not found, etc.)

**Download pipeline** (`main.py`)
- Background job system: POST to start job → poll for progress → GET to download zip
- Real progress counter (e.g. "3/9 files") returned to frontend
- PDFs saved to user's local machine as a `.zip` file

**AI Chat** (`agent.py`)
- Gemini 2.5 Flash via raw HTTP (REST API with `x-goog-api-key` header)
- Session-based conversation history stored in memory per session
- On first message: fetches selected PDFs, extracts text via `pdfplumber`, sends as context
- Subsequent messages continue the conversation using stored history
- System instruction sets the "Mining AI Analyst" persona (full analyst prompt saved in comments for later)

**Endpoints**
- `GET /companies` — list tracked companies
- `GET /companies/{name}/documents` — scrape and return PDF links
- `POST /companies/{name}/documents/download/start` — start background download job
- `GET /jobs/{id}/status` — poll job progress
- `GET /jobs/{id}/download` — retrieve completed zip
- `POST /chat` — send message to AI agent

### 3. Test Frontend (`backend/static/index.html`)
Plain HTML + vanilla JS, served by FastAPI. Temporary testing UI:
- Company dropdown
- Document list with checkboxes + select all
- Download selected as `.zip` with real progress bar
- Chat panel with session-based conversation

### 4. Run Script (`run.bat`)
Double-click to start the FastAPI backend. Opens at `http://127.0.0.1:8000`.

---

## Environment (`backend/.env`)
```
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_SECRET_KEY
GEMINI_API_KEY
```
All keys are dev-only and should be rotated before going to production.

---

## What's Planned Next

### Immediate — Next.js Frontend
Replace the plain HTML test UI with a proper React app using Next.js.
- **Rendering mode: client-side only** — no SSR (Server-Side Rendering) for now. All data fetching happens in the browser via the existing FastAPI endpoints. SSR will be added later when auth is needed (server needs to validate the session before rendering protected pages).
- Key pages:
  - **Home** — list of tracked companies
  - **Company page** (`/companies/[name]`) — company overview, summaries, documents, chat

### Per-Company Auto-Pipeline
When a user adds a new company, two summaries are auto-generated and saved to `agent_history`:
1. **Overview summary** — based on fetched PDFs + RAG knowledge base
2. **Management summary** — founders, key executives, track record, insider ownership (sourced from the AIF)

### RAG Knowledge Base (later)
Curated content to make the agent a specialist:
- Mining glossary (NPV, IRR, PEA, PFS, NI 43-101 terms)
- Red-flag pattern library
- Peer company comparison data
- Standards and benchmarks

Stored in Supabase `knowledge_base` table with pgvector embeddings. Agent retrieves relevant chunks at query time.

### Auth (later)
Supabase Auth (already in schema). Add login/signup when the app opens up beyond a single user. At that point, SSR will be enabled in Next.js so the server can verify auth before sending the page.

### Sensitivity / "What If" Sliders (later)
Interactive tool on the company report page letting the user stress-test the feasibility study assumptions:
- **Cost inflation slider** (0–50%) — inflates CAPEX and AISC proportionally, recalculates NPV and IRR in real time
- **Gold price slider** — adjusts the assumed gold price, recalculates NPV and IRR
- Both sliders work together so the user can model combined scenarios (e.g. +20% costs AND $2,000/oz gold)
- Key outputs shown: adjusted CAPEX, adjusted AISC, adjusted NPV, adjusted IRR
- Motivation: feasibility studies go stale fast (Kevin McLean: "two years old, almost not applicable") — this tool makes that risk visible and quantifiable

### Production Deployment (later)
- Rotate all API keys
- Deploy FastAPI backend to Render or Fly.io
- Deploy Next.js frontend to Vercel

---

## Current Limitations
- Only one company supported (First Mining Gold — hardcoded)
- No auth — single user only
- Chat history lost on server restart (in-memory only)
- PDFs not stored in cloud — local download only
- RAG knowledge base empty (not yet populated)
- Frontend is a temporary plain HTML page — Next.js not yet built
