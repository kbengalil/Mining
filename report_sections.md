# Report Sections — Mining AI Analyst

The 9 required sections of every company report, with all required bullet points.
This file is the source of truth for what the OVERVIEW_PROMPT in `backend/agent.py` must extract.

---

## 1. The Team

### 1a. Founders
- Who founded the company and when
- Background on each founder
- Current involvement and capacity

### 1b. Management Team *(per person)*
- Full name + title
- Total years of experience
- Key previous roles (company names + positions)
- Domain expertise

### 1c. Insider Ownership & Compensation
- Total shares owned by all directors & officers combined (number + % of total)
- CEO shares specifically (number + %)
- CEO compensation breakdown: Base Salary, Bonus, RSUs/PSUs, Options, Pension, Other, Total
- Strategic shareholders >5%: name, %, notable detail

---

## 2. Company Snapshot
- Commodity mined
- Countries/regions of operations
- Development stage (exploration / PEA / PFS / feasibility / production)

---

## 3. Key Project Metrics *(per project)*
- Resource: tonnes, grade, contained metal (M&I and Inferred separately)
- Reserves: tonnes, grade, contained metal
- NPV: amount, discount rate, metal price assumed, pre-tax or post-tax
- IRR: % and metal price assumed
- Initial capex
- Mine life
- Average annual production (state the period, e.g. years 1–5 vs LOM)
- Exploration upside (open along strike/depth, new zones, % of trend tested)

---

## 4. Financials

### 4a. Balance Sheet
- Every line item in the same order and grouping as the source document
- All subtotals and totals
- All figures expressed in millions (e.g. C$126.9M)
- Report date in section header

### 4b. Cash Flow & Capital
- Annual cash burn — operating activities only (annualized from most recent period)
- Annual cash burn — investing activities (MD&A stated budget if disclosed, otherwise annualized)
- Total cash burn (calc: operating + investing)
- Cash runway (calc: cash and cash equivalents only ÷ total annual burn, in years)
- Annual exploration / capital budget (if disclosed in MD&A)
- LOM net free cash flow (if disclosed — state pre-tax or post-tax)

### 4c. Project Economics *(from most recent technical report / PFS / feasibility)*
- NPV — all scenarios disclosed (discount rate, metal price assumed, pre-tax or post-tax)
- IRR — all scenarios disclosed (metal price assumed, pre-tax or post-tax)
- Payback period
- Initial capex
- AISC per oz (if disclosed)

### 4d. Share Structure
- Shares outstanding (with date)
- Warrants outstanding
- Options outstanding
- RSUs / PSUs / DSUs outstanding (combined)
- Fully diluted shares (calc: sum of all above)

---

## 5. Jurisdiction
- Countries/regions of main projects
- Sovereign risk factors mentioned in documents

---

## 6. Recent Developments
- Every material event from the last 6 months, with exact date, one bullet per event
- Covers: permits, agreements, financings, drill results, milestones, legal updates, partnerships

---

## 7. Valuation vs Peers
- Company's P/NAV or EV/production metric
- Peer group median for the same metric
- Implied discount or premium
- Peer companies named

---

## 8. Strategic Outlook
- M&A appetite (explicit management statements)
- Annual exploration / capex targets ($X/year)
- Production growth timeline and targets
- Dividend or buyback policy
- Any other stated priorities

---

## 9. Red Flags *(structured checklist — check every item)*

**Technical Studies:**
- Any PEA, PFS, or feasibility study older than 3 years
- Any Mineral Resource Estimate older than 3 years
- Any project still at PEA stage (inferred resources too speculative for reserves)

**Valuation:**
- NPV figures pre-tax only (flag if post-tax not stated)
- Government carried interests, royalties, taxes not netted out of investor-level NPV

**Dilution:**
- Private placements or public offerings in the last 3 years (list dates + amounts)
- Share count growing year over year
- Warrants or stock options outstanding
- Recent financings with warrant coverage (state ratio + strike price per financing)
- Distress financings at multi-year share price lows with heavy warrant coverage

**Legal & Environmental:**
- Indigenous rights disputes, permit challenges, or court proceedings
- Legacy environmental liabilities (tailings, contamination, remediation obligations)
- Any other ongoing litigation

**Financials:**
- Cash position not disclosed
- Exploration-stage runway: cash ÷ annual burn rate (months)
- Development/construction-stage funding gap: total capex vs total committed capital
- Significant debt or outstanding financial obligations
- Cash on hand vs total initial capex — state the gap explicitly

**Infrastructure:**
- No all-season road access to any project

**Jurisdiction:**
- Projects in high sovereign risk countries (outside Canada, USA, Australia, Scandinavia)

**Management:**
- Evidence of insider selling
- CEO/NEO compensation high relative to company stage (pre-revenue junior with base >$500K)
- Key decision-makers receiving salary + options + share awards pre-production
- Directors or officers with low or zero insider ownership

**Business Stage:**
- Company has never produced metal commercially
- Company entirely dependent on equity financing to fund operations
