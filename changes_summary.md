# Mining App — Changes Summary

## backend/agent.py

- **Capital budget source**: agent now checks MD&A first, then FS notes (e.g. Note 16 — commitments), before falling back to Q1×4 annualization
- **NPV/IRR source restricted**: NPV and IRR figures must come from the technical report (NI 43-101 / PFS / feasibility) only — investor presentations are explicitly excluded
- **All discount rate scenarios**: agent must include every discount rate scenario from the technical report (e.g. 3%, 5%, 7%) — not just one
- **`_filter_docs` broadened**: docs labeled PFS, PEA, or feasibility are now kept regardless of age (previously only "technical report" and "NI 43-101" were exempt from the 2-year filter)

## backend/main.py

- **PATCH endpoint added**: `PATCH /companies/{company_name}/overview/markdown` — allows direct editing of a report in the database without regenerating

## frontend/app/companies/[name]/page.js

- **Auto-archive on regenerate**: when regenerating from a live report page, the existing report is silently archived first before generating the new one
- **Regenerate from archive**: regenerating from an archive page creates a new report under the base company name using the same docs — no re-upload needed

## .claude/commands/report-review.md (skill)

- **Step 2 added**: check which documents were used; flag any excluded technical report or proxy circular and note what figures may be missing or secondhand
- **Step 7 added**: after all findings are reported, offer to fix errors directly in the report via the PATCH endpoint
- **Step numbering fixed**: removed duplicate Step 3, renumbered steps 4–7 correctly
