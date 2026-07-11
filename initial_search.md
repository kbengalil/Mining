# Initial Search — Data Fetching Improvements

Ways to make the scraping/fetching more comprehensive so the report doesn't miss things.

---

## 1. Always scrape the news page for PDFs
Currently the news page is fetched for text only. PDF links on the news page are ignored.
Fix: extract PDF links from the news page the same way we do for investor pages.
Impact: would have caught the 4 Osisko press releases (June 1, 2, 9, 24) that were missed in the first run.
Effort: small — one-line change in `find_pdf_links`.

## 2. Try standard IR sub-pages automatically
Instead of relying on Gemini to guess which pages exist, try all common IR paths and use the ones that return PDFs:
- `/investors/`
- `/investors/presentations/`
- `/investors/news/`
- `/investors/press-releases/`
- `/investors/reports-filings/`
- `/news/`
- `/press-releases/`

Impact: more consistent across companies, less reliance on Gemini guessing.
Effort: medium.

## 3. SEDAR+ for Canadian companies
Every Canadian public company must file all documents on SEDAR+ — it's legally required and comprehensive.
Companies can't omit unflattering documents there the way they can on their own IR page.
Adding SEDAR+ as a data source would be the single biggest quality jump, especially for financials and MICs.
Impact: highest — guaranteed complete document set for all Canadian juniors.
Effort: medium-high (need to build SEDAR+ scraper).

## 4. Crawl one level deeper
If an investor page links to a sub-page (not a PDF), follow that sub-page and look for PDFs there too.
Currently we only look for PDFs on the pages we visit — we don't follow links to nested pages.
Impact: catches documents buried in sub-sections.
Effort: medium.
