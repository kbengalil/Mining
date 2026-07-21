# Mining AI Analyst — App Context

## What the App Does

A web app that analyzes publicly traded mining companies for investors.
The user uploads PDF investor documents (financial statements, technical reports, MD&A, AIF, etc.) via the UI.
The app reads those documents via Gemini AI, scrapes the company's news page for recent headlines, and generates a structured 9-section research report.
Reports are cached in Supabase so repeat visits load instantly.
The app also generates charts extracted from corporate presentations.

---

## Tech Stack

- **Frontend:** Next.js (App Router), plain CSS, runs on localhost:3000
- **Backend:** Python FastAPI, runs on localhost:8000 (uvicorn with --reload)
- **AI:** Google Gemini 2.5 Flash (report generation, embeddings, chart extraction, company identification)
- **Database:** Supabase (PostgreSQL + pgvector for RAG, Storage for uploaded PDFs)
- **Scraping:** requests + BeautifulSoup (news page scraping, about page scraping)
- **PDF reading:** Gemini File API (uploads PDF bytes, reads inline)

---

## Project Structure

```
Mining/
├── backend/
│   ├── main.py          # FastAPI app — all endpoints
│   ├── agent.py         # Report generation, _filter_docs, OVERVIEW_PROMPT, RAG
│   ├── scraping.py      # fetch_pdf_bytes, scrape_news, scrape_about_pages, fallback crawling
│   ├── extractor.py     # Document extraction utilities
│   ├── charts.py        # Chart extraction from PDFs via Gemini
│   ├── ingest_transcript.py  # Generic script to ingest expert transcripts into RAG
│   ├── compare_reports.py    # Utility to diff two versions of a report
│   └── *.txt / *.md     # Expert framework source files (already ingested into RAG)
├── frontend/
│   └── app/
│       ├── page.js                        # Chat interface + right sidebar (Reports list)
│       └── companies/[name]/
│           ├── page.js                    # Company report page (progress + overview)
│           └── charts/page.js             # Charts page
├── report_sections.md   # Source of truth for the 9 report sections and required fields
├── tasks.md             # Pending bugs and features
└── changes_summary.md   # Log of changes made to the app
```

---

## Key Backend Endpoints

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/analyzed-companies` | List all saved reports (populates sidebar) |
| GET | `/companies/{name}/overview` | Get cached report from Supabase |
| POST | `/companies/{name}/overview/start?force=true` | Start a new analysis job |
| GET | `/overview-jobs/{job_id}` | Poll job status |
| DELETE | `/companies/{name}/overview` | Delete a report |
| PATCH | `/companies/{name}/overview/markdown` | Edit report markdown directly (no regeneration) |
| POST | `/companies/{name}/overview/archive` | Archive report (auto-numbers: [archived], [archived 2], etc.) |
| POST | `/companies/{name}/documents/upload` | Upload PDF files to Supabase Storage |
| GET | `/companies/{name}/documents/uploaded` | List uploaded docs for a company |
| POST | `/chat` | Chat with Gemini about mining stocks |
| GET | `/companies/{name}/charts` | Get cached charts |
| POST | `/companies/{name}/charts/start` | Start chart extraction job |
| GET | `/companies/{name}/charts/jobs/{job_id}` | Poll chart job status |

---

## Report Generation Flow

1. User uploads PDF docs via the UI → stored in Supabase Storage under `documents/{company-slug}/`
2. User triggers report generation (or it starts automatically after upload)
3. Frontend navigates to `/companies/[name]?job=<id>`
4. Background job runs `run_overview_job`:
   - **Docs:** Reads uploaded PDFs from Supabase Storage (primary source — no web crawling)
   - **Filter:** `_filter_docs()` removes irrelevant docs (ESTMA, old docs, garbage labels, deduplicates AIFs/MICs)
   - **Read:** Downloads each PDF and uploads to Gemini File API, reads in parallel (up to 5 at a time)
   - **Scrape:** Scrapes management/about pages for supplementary team info
   - **News:** Scrapes company news page for recent headlines
   - **RAG:** Queries Supabase pgvector for relevant expert knowledge (7 experts)
   - **Generate:** Sends everything to Gemini with OVERVIEW_PROMPT, gets 9-section markdown report
   - **Save:** Stores report + source_urls in Supabase `company_overviews` table
5. Frontend polls job every second, shows live progress steps
6. On completion, renders the markdown report

**Fallback (server restart):** If `dynamic_companies` is lost from memory and Regenerate is clicked, the backend recovers the base URL from Supabase and re-crawls investor pages to find PDFs. This is the only scenario where web crawling still runs.

---

## The 9-Section Report

1. The Team — Founders / Management Team / Insider Ownership & Compensation (3 sub-sections)
2. Company Snapshot — what they mine, where, development stage
3. Key Project Metrics — reserves, NPV, IRR, capex, mine life, exploration upside per project
4. Financials — cash, debt, shares, warrants, every financing event, cash flow, budgets
5. Jurisdiction — countries, sovereign risk factors
6. Recent Developments — all material events last 6 months with dates
7. Valuation vs Peers — P/NAV or EV/production vs named peer group
8. Strategic Outlook — M&A plans, production targets, dividend/buyback policy
9. Red Flags — structured checklist: technical studies, valuation, dilution, legal, financials, infrastructure, jurisdiction, management, business stage

See `report_sections.md` for the full spec of required fields per section.

---

## Document Filter (`_filter_docs` in agent.py)

Runs before report generation to reduce noise. Key rules:
- **Skip always:** ESTMA filings, test PDFs, "forced labour", "voluntary carbon", "supply chain" docs, garbage nav labels, proxy circulars
- **AIFs:** keep only the most recent Annual Information Form (by year in label)
- **MICs:** keep only the most recent Management Information Circular
- **Press releases:** keep last 6 months, minimum 5
- **Old docs:** drop financial docs where all years in label ≤ today - 4 years
- **Technical reports (PFS, PEA, feasibility, NI 43-101):** always kept regardless of age
- **Never skip:** corporate presentations, fact sheets (critical — contain charts)

---

## RAG Knowledge Base

7 expert frameworks ingested into Supabase `knowledge_base` table (pgvector):
1. Rick Rule — 2 symposium talks
2. Kevin McLean
3. David Lotan
4. Don Durant
5. Bob Quartermain
6. Jonathan Goodman
7. Michael Gentile — 12 chunks

Generic ingest script: `backend/ingest_transcript.py`

---

## In-Memory State (lost on server restart)

- `overview_jobs` dict — running/completed job status
- `dynamic_companies` dict — company configs (base_url, investor_pages, etc.)

On restart, job IDs become invalid — frontend polls get 404 (known bug, see tasks.md).

---

## Supabase Tables & Storage

- `company_overviews` — `company_name`, `overview_markdown`, `source_urls` (array of PDF URLs), `generated_at`
- `knowledge_base` — RAG chunks: `content`, `embedding` (pgvector), `title`, `speaker`, `source_url`
- `documents` Storage bucket — uploaded PDFs stored under `{company-slug}/{filename}.pdf`

Archived reports use prefix `_` and suffix `[archived N]`, e.g. `_Equinox Gold Corp. [archived 2]`.

---

## Known Issues & Pending Tasks

See `tasks.md` for the full list. Key ones:

**Bugs:**
- Frontend polls forever on 404 after server restart (needs `r.ok` check in poll functions)
- Green checkmarks (✓) don't show during live job — `selected_pdfs` not updated in `run_overview_job`

**Features:**
- Charts generation freezes if Gemini is slow — needs background job pattern (same as report)
- "Thinking..." in chat has no progress indicator — needs animated indeterminate bar

---

## Important Constraints

- API keys are in `.env` — never paste in chat, never commit
- Do NOT push/tag git without explicit user request
- Corporate presentations and fact sheets must NEVER be filtered out (they contain chart data)
- NPV/IRR figures must only come from the technical report (NI 43-101 / PFS / feasibility) — not investor presentations
- Gemini timeout for report generation is set to 1000s
- Gemini 503 errors are caught in chat endpoint and shown as user-friendly message
