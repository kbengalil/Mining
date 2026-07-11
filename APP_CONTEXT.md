# Mining AI Analyst — App Context

## What the App Does

A web app that analyzes publicly traded mining companies for investors.
The user pastes a company's investor relations URL (e.g. https://www.equinoxgold.com) into a chat interface.
The app crawls the company website, collects investor PDFs, reads them via Gemini AI, and generates a structured 11-section research report.
Reports are cached in Supabase so repeat visits load instantly.
The app also generates charts extracted from corporate presentations.

---

## Tech Stack

- **Frontend:** Next.js (App Router), plain CSS, runs on localhost:3000
- **Backend:** Python FastAPI, runs on localhost:8000 (uvicorn with --reload)
- **AI:** Google Gemini 2.5 Flash (report generation, embeddings, chart extraction, company identification)
- **Database:** Supabase (PostgreSQL + pgvector for RAG)
- **Crawling:** Playwright (JS-rendered sites) + requests (fast fallback)
- **PDF reading:** Gemini File API (uploads PDF bytes, reads inline)

---

## Project Structure

```
Mining/
├── backend/
│   ├── main.py          # FastAPI app — all endpoints
│   ├── agent.py         # Report generation, _filter_docs, OVERVIEW_PROMPT, RAG
│   ├── scraping.py      # PDF crawling, BFS crawler, find_pdf_links, scrape_news
│   ├── charts.py        # Chart extraction from PDFs via Gemini
│   └── bob_quartermain_framework.txt  # Expert framework (not yet ingested into RAG)
├── frontend/
│   └── app/
│       ├── page.js                        # Chat interface + right sidebar (Reports list)
│       └── companies/[name]/
│           ├── page.js                    # Company report page (progress + overview)
│           └── charts/page.js             # Charts page
└── tasks.md             # Pending tasks (see below)
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
| POST | `/companies/{name}/overview/archive` | Archive report (auto-numbers: [archived], [archived 2], etc.) |
| POST | `/chat` | Chat with Gemini about mining stocks |
| GET | `/companies/{name}/charts` | Get cached charts |
| POST | `/companies/{name}/charts/start` | Start chart extraction job |
| GET | `/companies/{name}/charts/jobs/{job_id}` | Poll chart job status |

---

## Report Generation Flow

1. User pastes URL in chat → backend identifies company via Gemini → returns job_id
2. Frontend navigates to `/companies/[name]?job=<id>`
3. Background job runs `run_overview_job`:
   - **Crawl:** BFS crawl of investor pages to find all PDFs
   - **Filter:** `_filter_docs()` reduces 80-100 PDFs to ~30 relevant ones (skips ESTMA, old docs, garbage labels, deduplicates AIFs/MICs, limits press releases to 6 months/min 5)
   - **Read:** Uploads each selected PDF to Gemini File API, reads in parallel (up to 5 at a time)
   - **Scrape:** Scrapes management/about pages via Playwright
   - **News:** Scrapes company news page for recent headlines
   - **RAG:** Queries Supabase pgvector for relevant expert knowledge
   - **Generate:** Sends everything to Gemini with OVERVIEW_PROMPT, gets 11-section markdown report
   - **Save:** Stores report + source_urls in Supabase `company_overviews` table
4. Frontend polls job every second, shows live progress steps
5. On completion, renders the markdown report

---

## The 11-Section Report

1. Recent Developments — all material events last 6 months with dates
2. Company Snapshot — what they mine, where, development stage
3. Founders — background, current involvement
4. Management Team — each executive: title, years experience, prior roles
5. Insider Ownership & Compensation — CEO comp breakdown from MIC, strategic shareholders
6. Key Project Metrics — reserves, NPV, IRR, capex, mine life, exploration upside per project
7. Financials — cash, debt, shares, warrants, every financing event, cash flow, budgets
8. Jurisdiction — countries, sovereign risk factors
9. Valuation vs Peers — P/NAV or EV/production vs named peer group
10. Strategic Outlook — M&A plans, production targets, dividend/buyback policy
11. Red Flags — structured checklist: technical studies, valuation, dilution, legal, financials, infrastructure, jurisdiction, management, business stage

---

## Document Filter (`_filter_docs` in agent.py)

Runs before report generation to reduce noise. Key rules:
- **Skip always:** ESTMA filings, test PDFs, "forced labour", "voluntary carbon", "supply chain" docs, garbage nav labels
- **AIFs:** keep only the most recent Annual Information Form (by year in label)
- **MICs:** keep only the most recent Management Information Circular
- **Press releases:** keep last 6 months, minimum 5
- **Old ESG:** skip dated ESG reports older than 2 years
- **Never skip:** corporate presentations, fact sheets (critical — contain charts)

---

## In-Memory State (lost on server restart)

- `overview_jobs` dict — running/completed job status
- `dynamic_companies` dict — crawled company configs (base_url, investor_pages, etc.)

On restart, `dynamic_companies` is recovered from Supabase `source_urls` when Regenerate is clicked.
Job IDs become invalid on restart — frontend polls get 404.

---

## Supabase Tables

- `company_overviews` — columns: `company_name`, `overview_markdown`, `source_urls` (array of PDF URLs), `generated_at`
- `documents` — RAG chunks: `content`, `embedding` (pgvector), `source`, `company`

Archived reports are stored with prefix `_` and suffix `[archived N]`, e.g. `_Equinox Gold Corp. [archived 2]`.

---

## Known Issues & Pending Tasks

See `tasks.md` for the full list. Key ones:

**Bugs:**
- Frontend polls forever on 404 after server restart (needs `r.ok` check in poll functions)
- Green checkmarks (✓) never show on document list — `selected_pdfs` not updated after crawl
- `_filter_docs` misses some bad docs (ESTMA via filename, multiple AIFs, ancient quarterly filings)

**Features:**
- Charts generation freezes if Gemini is slow — needs background job pattern (same as report)
- "Thinking..." in chat has no progress indicator — needs animated indeterminate bar

**Content:**
- Bob Quartermain expert framework in `bob_quartermain_framework.txt` — not yet ingested into RAG

---

## Important Constraints

- API keys are in `.env` — never paste in chat, never commit
- Do NOT push/tag git without explicit user request
- Corporate presentations and fact sheets must NEVER be filtered out (they contain chart data)
- Gemini timeout for report generation is set to 1000s (was hitting 120s timeout on large reports)
- Gemini 503 errors are caught in chat endpoint and shown as user-friendly message
