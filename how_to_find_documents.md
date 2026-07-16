# How to Find Investor Documents for a Mining Company

This guide explains how to find the documents needed to generate a report in the Mining AI Analyst app.

The documents depend on **where the stock is listed** (not where the mine is located).

---

## Which Set of Documents Do You Need?

| Listed on | Filing System | Standard |
|---|---|---|
| TSX, TSX-V, CSE (Canada) | SEDAR+ | Canadian — use the 6-doc set below |
| NYSE, NASDAQ, NYSE American (USA only) | EDGAR | US — use the US set below |
| Dual-listed (TSX + NYSE) | SEDAR+ | Use SEDAR+ — Canadian rules apply |
| ASX (Australia) | ASX website | JORC Code — similar to NI 43-101 |

> **Dual-listed companies** (e.g. Vizsla Silver on TSX + NYSE American) follow Canadian rules. Use SEDAR+, not EDGAR.

---

## Canadian-Listed Companies — The 6 Documents

| # | Document | Where to Find It |
|---|---|---|
| 1 | Corporate Presentation | Company IR website |
| 2 | Management Information Circular (MIC) | SEDAR+ |
| 3 | Financial Statements | SEDAR+ |
| 4 | MD&A | SEDAR+ |
| 5 | Annual Information Form (AIF) | SEDAR+ |
| 6 | NI 43-101 Technical Report | SEDAR+ |

---

## USA-Only Listed Companies — The 4 Documents

For companies listed **only** on NYSE, NASDAQ, or NYSE American (no Canadian listing), use EDGAR (edgar.sec.gov) instead of SEDAR+.

| # | Document | Replaces | Where to Find It |
|---|---|---|---|
| 1 | Corporate Presentation | Corporate Presentation | Company IR website |
| 2 | DEF 14A (Proxy Statement) | MIC | EDGAR |
| 3 | 10-K Annual Report | FS + MD&A + AIF + NI 43-101 | EDGAR |
| 4 | S-K 1300 Technical Report (if filed separately) | NI 43-101 | EDGAR or company website |

> The **10-K** is an all-in-one document — it contains the financial statements, MD&A, risk factors (equivalent of AIF), and the S-K 1300 technical disclosure. You do not need separate FS and MD&A files.

> **Foreign private issuers** (non-US companies listed on NYSE/NASDAQ) file a **20-F** instead of a 10-K. It serves the same purpose.

### How to Find on EDGAR

1. Go to **edgar.sec.gov**
2. Click **Company Search**
3. Type the company name → click Search
4. Filter by form type: **10-K** (or **20-F** for foreign issuers), **DEF 14A** for the proxy
5. Click the most recent filing → click the document link to get the PDF URL

---

## Step 1 — Find the Corporate Presentation on the Company Website

1. Go to the company's website (e.g. vizslasilvercorp.ca)
2. Click **Investors** in the top menu
3. Look for a link called **Corporate Presentation** or **Investor Presentation**
4. Click to open the PDF and copy the URL from your browser's address bar

> If you can't find it on the website, search Google: `"Vizsla Silver" corporate presentation filetype:pdf`

---

## Step 2 — Find the Other 5 Documents on SEDAR+

SEDAR+ is Canada's official securities filing system. Every Canadian public company must file all financial documents there. Go to **sedarplus.ca**

### 2a — Find the Company Profile

1. Click **Search SEDAR+** in the top menu
2. Click **Profiles**
3. Type the company name (e.g. "Vizsla Silver") in the Profile name box
4. Click the search icon
5. Click on the company name in the results

### 2b — Go to Documents

On the company profile page, click **Documents** at the top.

You will see a long list of all filings. Use the **Filing type** dropdown to filter — this saves a lot of scrolling.

---

## Finding Each Document

### Financial Statements (Annual)
- **Filing type:** `Annual financial statements`
- Pick the **most recent** one (highest year)
- Click **Generate URL** → copy that URL

### MD&A (Annual)
- **Filing type:** `Annual MD&A`
- Pick the **most recent** one
- Click **Generate URL** → copy that URL

### Annual Information Form (AIF)
- **Filing type:** `Annual information form`
- Pick the **most recent** one
- Click **Generate URL** → copy that URL

### Management Information Circular (MIC)
- **Filing type:** `Management proxy materials`
- Look for a file named **"Information Circular"** or **"Management Information Circular"**
- Pick the **most recent annual** one (not a Special Meeting circular — those are for specific votes, not the annual proxy)
- Click **Generate URL** → copy that URL

> **How to tell the difference:** The annual MIC covers CEO compensation and director elections. A Special Meeting circular is for a specific vote (e.g. merger approval) and will say "Special Meeting" in the name. Use the annual one.

### NI 43-101 Technical Report
- **Filing type:** `Technical report(s) (NI 43-101) - continuous disclosure`
- Look for a file named **"Technical report (NI 43-101)"** — it will be large (10MB–50MB)
- Ignore the "Certificate of qualified person" and "Consent of qualified person" files — those are supporting docs, not the report itself
- Pick the **most recent** one
- Click **Generate URL** → copy that URL

---

## Step 3 — Paste the URLs into the App

Go to the company page in the Mining AI Analyst app and paste each URL into the correct slot:

- Corporate Presentation → paste the presentation URL
- Management Information Circular → paste the MIC URL
- Financial Statements → paste the FS URL
- MD&A → paste the MD&A URL
- Annual Information Form → paste the AIF URL
- NI 43-101 Technical Report → paste the technical report URL

Then click **Generate Report**.

---

## Tips

- **Vizsla Silver has an April 30 year end** — so their annual filings appear in July/August each year, not in the usual March–April window.
- **If a document is not available** (e.g. no NI 43-101 yet for an early-stage explorer), leave that slot blank. The report will still generate with fewer documents.
- **Always use the most recent version** of each document — older filings give stale data.
- **EDGAR** is the US equivalent of SEDAR+ (for NYSE/NASDAQ-listed companies). Use it for US-listed companies that don't file on SEDAR+.
