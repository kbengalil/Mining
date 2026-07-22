# Product Ideas — Mining AI Analyst

Sources: Perplexity + ChatGPT + Gemini + Opus + Fable 5 (2026-07-07).

---

## Strong ideas — build these

**Side-by-side company comparison**
Compare 2–5 companies on the same metrics: deposit quality, jurisdiction, capex, dilution, study freshness, financing risk.
High value, high differentiation. Buildable with current stack.

**Watchlist + change detection**
Re-run analysis when a new filing lands (AIF, MIC, MD&A, presentation, press release).
Highlight what changed since the last run. Turns the app from one-time use to weekly habit.

**Exportable diligence memo**
One-click PDF/Word export of the report in IC memo format: thesis, key risks, catalysts, valuation, open questions.
High value for analysts and small funds.

**Red flag scoring**
Make each red flag explicit with a severity score and explanation of why it matters.
Currently flags are factual observations — adding severity makes triage faster.

**Portfolio / watchlist view**
Users tag companies by stage, commodity, jurisdiction, risk profile.
Rank by conviction or red flag count. Drives retention.

---

## Good ideas — consider for later

**"Ask the filing" chat after report generation**
Already partially done. After the report, user can ask grounded questions linked to specific documents.
Worth making more prominent in the UI.

**Source traceability**
Every claim links to the exact PDF page or paragraph.
Hard to implement well but high trust signal — especially for analysts.

**Investment fit triage**
On first use, ask: explorer / developer / producer / royalty / turnaround?
Tailor analysis depth and framing accordingly.

**Missing diligence flagging**
Auto-detect gaps: "No recent metallurgy update", "No sensitivity table", "No jurisdiction permitting discussion."
Additive to existing red flags.

**Valuation lens modes**
Let user switch between conservative, contrarian, quality-focused interpretation
using the Rick Rule / Kevin McLean frameworks already in the RAG.

---

## Monetization model (Perplexity suggestion)

- **Free tier**: single company, single report
- **Analyst tier**: watchlists, comparisons, alerts, CSV export, source citations, batch coverage
- **API tier**: structured outputs for funds and newsletter operators
- **IC mode**: share report, add notes, vote on conviction (team feature)

---

## Skip for now

- Financing/dilution forecasting module — partially covered by existing red flags
- Quality of disclosure score — too subjective for now
- Screening API — post-product-market-fit feature

---

## ChatGPT additions (ideas not in Perplexity)

**Facts dashboard (adapted from ChatGPT's Investment Score idea)** ⭐
No AI scores or opinions. Instead, a structured table of raw facts at the top of every report:
- Financing: Cash / Capex / Gap
- Dilution: number of raises, warrants outstanding
- Study stage: PEA / PFS / Feasibility
- Jurisdiction: country
- Management: mines built, previous companies

User sees the facts at a glance and draws their own conclusion. Red flags remain the only AI opinion layer.

**Technical report diffing** ⭐
Upload two versions of the same feasibility study (e.g. 2022 vs 2025).
AI highlights only meaningful changes: strip ratio up, capex +40%, IRR down, recovery improved.
ChatGPT noted this hasn't been done well anywhere. Strong differentiator.

**Timeline mode**
Auto-extract development milestones from documents: PEA → PFS → Feasibility → Permit → Construction.
Show what changed at each stage (capex, NPV, reserves).
Useful for understanding how a company has evolved and whether it is on track.

**Valuation sandbox**
Let users adjust gold price, discount rate, capex inflation, FX, recovery, production schedule.
NPV updates instantly with approximate sensitivity.
Even rough numbers are more useful than a static figure.

**Confidence scoring**
Every extracted fact shows a confidence % and its source (PDF page number).
When two documents conflict, flag it: "Recovery: ~87% — Confidence 54% — conflicting figures between Feasibility and Presentation."
Builds trust, especially for analysts.

**Mine economics benchmarking**
Compare each project against peers automatically.
Instead of "IRR = 24%", show "Top 20% among comparable Canadian open-pit gold projects."
Requires building a project database over time.

**Management intelligence profiles**
Go beyond bios. Build track records: previous companies, mine builds, exits, failures, dilution history, board overlaps.
Mining investing is often management investing — this is high signal.

**Cross-document Q&A**
"Has this CEO built a mine before?" / "How many times has this company diluted shareholders?"
Requires synthesizing across multiple documents, not just searching within one.
Already partially possible — worth making more prominent.

**Decision memo**
After analysis, generate an investment memo: thesis (3 bullets), reasons to avoid, catalysts next 12 months,
key unknowns, questions for management, bull/base/bear case.
More actionable than a report — closer to what a fund analyst would write.

**"Explain like I'm a mining analyst" glossary**
Every technical term is clickable: NPV, strip ratio, inferred resource, AISC, etc.
Expands to: what it is, why it matters, typical range, how it's manipulated, how professionals use it.
Broadens the audience without cluttering the main report.

---

## Gemini additions (ideas not in Perplexity or ChatGPT)

**Valuation reverse-engineering** ⭐
Given the current stock price, calculate the implied value per ounce of gold in the ground.
e.g. "At $0.47/share the market is pricing this deposit at $28/oz — a 90% discount to NAV."
Very specific to mining, very useful. No AI opinion needed — just math from the documents + live price.

**Permit & regulatory timeline tracker**
Extract permit milestones from documents: environmental assessments, water licenses, indigenous agreements.
Flag unexplained delays. Junior miners live and die by approvals — this is often the biggest risk not visible in the numbers.

**Map integration**
Extract claim coordinates from technical reports and plot them on a map.
Show nearby producing mines and recent discoveries in the same district (Abitibi, Golden Triangle, etc.).
Lets users validate or challenge "nearology" marketing claims with geography.

**Drill hole data parsing**
Extract assay results from press releases automatically.
Compare gram-metre intercepts against the company's own historical results and regional baselines.
High value for exploration-stage companies where drill results are the main news flow.

**Dilution & insider transaction overlay**
Chart showing share count over time with insider buy/sell transactions plotted on top.
Immediately shows whether management bought when they diluted or sold before a decline.
Visual, factual, no AI opinion needed.

**Red flags first (UX)**
Simple UX change: move the red flags section to the top of the report, before the upside.
Currently buried at the bottom — risks should be the first thing a user sees.

---

## Fable 5 additions (ideas not in previous models)

**Second-model verification pass** ⭐
We already run both Gemini and Claude — use disagreement between them as a signal.
When two models extract different numbers for the same figure (e.g. NPV, capex, salary),
flag that figure as "unverified" instead of showing one confidently.
"One confidently wrong NPV in a screenshot on X kills you." Directly actionable with our current stack.

**Quantitative red-flag scoring as a screener**
Move from checklist prose to numeric composites: dilution score, capital-gap ratio, study staleness in months.
This enables a screener: "show me developers in Tier-1 jurisdictions with post-tax IRR > 25% and no capital gap."
A screener is a product in itself — different from just reading one report at a time.

**M&A comp benchmarking**
Benchmark each project against historical M&A transactions:
"Developers in this jurisdiction have been acquired at $X–$Y per oz historically."
More specific and actionable than peer benchmarking against active companies.

**"Five questions the expert would ask management"**
Per company, generate the specific questions Rick Rule (or Kevin McLean) would ask in a management call.
Good demo material, defensible differentiator, and directly uses our existing RAG.

**Cost inflation / sensitivity sliders** ⭐ (Rick Rule session 2026-07-08)
Interactive tool on the company report page. Two sliders: cost inflation % (0–50%) and gold price assumption.
Both recalculate CAPEX, AISC, NPV, and IRR in real time.
Core insight: feasibility studies go stale fast — Kevin McLean: "two years old, almost not applicable."
This makes that risk visible and quantifiable. Extends #2 (NPV recalculation) with the cost-escalation dimension.
OS will never build this — showing users how bad the numbers get under stress is not in their interest.

**Compliance / disclaimer architecture**
As we add fair-value ranges, scores, and NPV recalculations we drift toward investment advice.
Get the disclaimer architecture right early — frame all outputs as research, not recommendations.
Worth doing before launching to paying users.

**IR pages are marketing, filings are law**
Key framing for SEDI/SEDAR+ priority: IR pages can quietly omit unflattering documents.
SEDAR+ can't. This is why external data feeds matter beyond just "more data."

---

## Opus additions (ideas not in Perplexity, ChatGPT, or Gemini)

**The core moat framing** (strategic, not a feature)
Opus identified the real differentiator clearly:
1. Standardized, comparable output across the whole sector
2. Domain red flags a beginner wouldn't know to look for
3. The expert valuation lens (Rick Rule / Kevin McLean)
The pro-grade product is the one that catches what companies didn't disclose —
moving from "reflecting company marketing" to "grounding in external truth."
Tagline: *"I checked whether the company's story survives contact with reality."*

**NPV recalculation at spot price, post-tax** ⭐
More specific than "valuation sandbox." Companies headline a pre-tax NPV at an inflated metal price.
Pull live spot prices, let the user set their own metal-price deck and discount rate, re-derive.
Output: "Osisko shows $2.1B NPV at $1,900 gold pre-tax. At today's $X spot, post-tax, 8% discount rate: $Y."
Opus called this the single strongest wedge — genuinely hard to DIY, worth the subscription alone.
Requires a small sensitivity model, not just the LLM.

**External data feeds: SEDI + SEDAR+** ⭐
The AIF tells you insider ownership as of a stale date. The real signal is live data:
- **SEDI** (Canada): live insider buying/selling transactions
- **SEDAR+**: recent financings, placements, new filings
Fully-diluted share count (warrants + options) and market cap/EV feeds turn dilution
and capital-gap flags from "as-reported" to "as-verified." Highest-signal data in junior mining.

**Stage-tailored report templates**
Explorer, Developer, Producer, and Royalty are different games — one template doesn't fit all:
- Explorer: jockey quality + land package + drill results
- Developer: financing gap + permitting timeline
- Producer: AISC, guidance, reserve life, FCF
- Royalty: portfolio quality + GEO growth
Detect the stage automatically and switch the template. Sharpens every report immediately.

**Lassonde curve positioning**
Score each company against the Lassonde curve (the standard mining stock lifecycle model).
Shows where the company sits in its lifecycle and what the typical next catalyst is.
Defensible differentiator — pairs naturally with the expert lens.

**Citations as table stakes** (emphasis)
Opus was most emphatic about this: a hallucinated NPV or reserve figure is fatal to trust.
Every extracted number must carry a source-doc + page citation the user can click to verify.
"If you build nothing else this quarter, build this."

**Research depth vs. triage — open question**
Worth pressure-testing with users before building:
- Do they need to go deep on one company? (depth roadmap)
- Or screen 40 companies fast? (triage/coverage roadmap)
The two roadmaps diverge significantly. Opus recommends 5 user conversations to find out.

---

## Overall workflow framing (ChatGPT)

The strongest long-term framing is not "AI that reads documents" but becoming the
**structured intelligence layer for the mining sector**:

> Universe → Screen → Compare → Deep Dive → Monitor → Decision

Roadmap stages:
1. **Research assistant** (current MVP) — standardized company analyses from filings
2. **Research workspace** — comparisons, timelines, watchlists, alerts, collaborative notes
3. **Sector intelligence platform** — screening across companies, benchmarking, trend detection
4. **Decision support** — valuation scenarios, portfolio exposure, thesis tracking

---

## Consolidated Ranked List (all sources)

**Tier 1 — Build next**
1. Source citations on every number — ChatGPT, Opus, Fable
2. NPV recalculation at spot price, post-tax — Opus, Fable
3. Side-by-side company comparison — ALL 5 models
4. Watchlist + change detection — ALL 5 models
5. SEDI + SEDAR+ external data feeds — Opus, Fable
6. Second-model verification pass — Fable
7. CEO comepesantion over time

**Tier 2 — Strong follow-ons**
7. Stage-tailored report templates — Opus, Fable
8. Exportable one-page memo — Perplexity, ChatGPT, Fable
9. Quantitative red-flag scoring / screener — Fable
10. Valuation reverse-engineering (implied $/oz) — Gemini
11. Facts dashboard at top of report — ChatGPT
12. Technical report diffing — ChatGPT
13. Red flags first (UX) — Gemini
14. Permit & regulatory timeline tracker — Gemini
15. Cost inflation + discount rate / sensitivity sliders — Rick Rule session (2026-07-08)
16. Compliance / disclaimer architecture — Fable

**Tier 3 — Later**
17. Management intelligence profiles — ChatGPT, Opus
18. Timeline mode — ChatGPT
19. Mine economics benchmarking — ChatGPT
20. M&A comp benchmarking — Fable
21. Dilution & insider chart overlay — Gemini
22. Map integration — Gemini
23. Lassonde curve positioning — Opus
24. "Five questions the expert would ask" — Fable
25. Clickable glossary — ChatGPT
26. Cross-document Q&A — ChatGPT
27. Portfolio view — Perplexity, ChatGPT
28. Investment fit triage — Perplexity
29. Drill hole data parsing — Gemini
30. Missing diligence flagging — Perplexity
31. Valuation lens modes — Perplexity, Opus, Fable
