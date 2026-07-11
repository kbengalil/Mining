# Pending Tasks

## Bugs

- [ ] **Frontend polls forever on 404** — After a server restart, in-memory jobs are wiped. Pages still polling for those jobs get 404 forever because the poll only stops on `status === "done"` or `status === "error"`. Fix: check `r.ok` in the poll function; if 404, stop polling and show an error with a Retry button. Affects both the report page and the charts page.

- [x] **Green checkmarks not showing (cached view)** — `selectedPdfs` never set when loading from cache. Fixed: added `setSelectedPdfs(Object.keys(map))` in the cached branch of company page.

- [ ] **Green checkmarks not showing (job view)** — `job["selected_pdfs"]` is never updated after crawl in `run_overview_job`. Fix: add `job["selected_pdfs"] = list(_filter_docs(pdf_docs).keys())` after crawl updates `pdf_docs`.

- [ ] **`_filter_docs` not catching all bad docs** — Issues seen across reports:
  - ESTMA file slipped through (anchor text probably didn't match the regex)
  - All 4 AIFs included instead of just the latest (AIF_RE not matching anchor text labels)
  - 2015 quarterly financials included (ancient docs, no cutoff rule for old filings)
  - "EQX-Test-PDF" showing in Equinox docs (test file, should be caught by SKIP_RE but label format `EQX-Test-PDF` may not match)
  - Equinox still shows 95 docs total (filter too permissive for large sites with many ESTMA/ESG/compliance files)
  - Mundoro: Q4 2022 FS (4 years old), Form of Proxy, Financial Statements Request Form all fed to Gemini

- [ ] **Performance: `_extract_pdfs_wix` runs for ALL companies** — Removed Wix detection so enhanced extraction always runs. Non-Wix sites hit button-click timeouts (5s each, up to 20 buttons × 3 texts = potential 5 min delay). Fix: restore lightweight Wix detection OR reduce button-click timeout significantly for non-Wix sites.

- [ ] **Hash-named Wix doc labels unreadable** — Wix stores PDFs with hash filenames (e.g. `33dbb0_1281c41c...`). Users can't tell what the doc is. Fix: try to infer label from PDF content (first page title) or map via Wix document metadata.

## Features

- [ ] **Charts generation as background job** — Right now charts freeze if Gemini is slow and navigating away kills the request. Fix: make it a background job like report generation (kick off → return job_id → poll → show error/retry on failure). User can then navigate away mid-generation.

- [ ] **"Thinking..." progress indicator in chat** — When user pastes a URL, the chat shows "Thinking..." with no feedback. Add an animated indeterminate bar so the user knows it's running.

- [ ] **Progress bar for document reading (chat left panel)** — Show reading progress visually in the left panel, not just the X/32 number. (User said: do later)

- [x] **Report prompt consistency** — "3-5 bullet points" in Financials, Recent Developments, and Key Project Metrics gives Gemini discretion, causing different detail levels across runs. Fix: replace with explicit "list ALL X" extraction rules for those sections (e.g. "List EVERY financing event — date, type, amount, shares issued"). Red Flags section is already well-specified via checklist.

## Content

- [ ] **Ingest Bob Quartermain framework into RAG knowledge base** — Framework is in `backend/bob_quartermain_framework.txt`. Needs to be chunked and embedded into Supabase pgvector.

## Fixed This Session

- [x] **Wix PDF extraction** — Mundoro went from 4 to 19 docs. Root cause: Wix detection always failed. Fix: removed detection, always use `_extract_pdfs_wix` with synchronous `expect_popup()` instead of async `page.on("popup")`.
- [x] **News missing full month names** — Regex only matched 3-letter abbreviations (Jul, Apr). Sites using full names (July, April) had those articles skipped. Fixed: regex now handles both forms.
- [x] **Stop button** — Added to both chat left panel and company report page header.
- [x] **500 error on /chat** — `detect_company_intent` Gemini timeout crashed the whole request. Fixed: wrapped in try/except, falls through to URL-based detection.
