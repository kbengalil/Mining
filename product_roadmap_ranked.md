# Product Ideas — Ranked by Significance
All sources: Perplexity, ChatGPT, Gemini, Opus, Fable 5

---

## Tier 1 — Build next (highest impact)

1. **Source citations on every number** — ChatGPT, Opus, Fable
   Every NPV, reserve figure, salary links to document + page. Trust infrastructure. All three called it non-negotiable.

2. **NPV recalculation at spot price, post-tax** — Opus, Fable
   Pull live spot prices, let user set discount rate, rebuild DCF from the technical study. Show NPV at spot vs. company's inflated deck. The single strongest wedge — deterministic math, no hallucination risk.

3. **Side-by-side company comparison** — Perplexity, ChatGPT, Gemini, Opus, Fable
   Compare 2–5 companies on NPV, IRR, capex, EV/oz, dilution, jurisdiction, insider ownership. All 5 models agreed.

4. **Watchlist + change detection** — Perplexity, ChatGPT, Gemini, Opus, Fable
   Re-run analysis when new filing lands. Alert on what changed. Turns app from one-time use to weekly habit. All 5 agreed.

5. **SEDI + SEDAR+ external data feeds** — Opus, Fable
   Live insider buying/selling (SEDI) and recent financings (SEDAR+). IR pages can omit unflattering documents — filings can't. Turns flags from "as-reported" to "as-verified."

6. **Second-model verification pass** — Fable
   Use disagreement between Gemini and Claude as an "unverified" flag on extracted figures. Directly actionable now — we already run both models.

---

## Tier 2 — Strong follow-ons

7. **Stage-tailored report templates** — Opus, Fable
   Explorer / Developer / Producer / Royalty each need different reports and different red flag weights. Detect stage, switch template. Cheap to build, big quality jump.

8. **Exportable one-page memo** — Perplexity, ChatGPT, Fable
   Bull case / bear case / key risks / open questions as PDF. What a fund analyst forwards. Also organic marketing if watermarked.

9. **Quantitative red-flag scoring as screener** — Fable
   Move from checklist prose to numeric composites: dilution score, capital-gap ratio, study staleness in months. Enables: "show me developers in Tier-1 jurisdictions with post-tax IRR > 25% and no capital gap." A screener is a product in itself.

10. **Valuation reverse-engineering — implied $/oz** — Gemini
    Given current stock price, calculate what the market is implying per oz in the ground. "At $0.47/share the market prices this deposit at $28/oz — 90% discount to NAV." Factual math, no AI opinion.

11. **Facts dashboard at top of report** — ChatGPT (adapted, no AI scores)
    Structured table of raw facts: Cash / Capex / Gap / Dilution history / Study stage / Jurisdiction / Management track record. User draws own conclusion. No scores, no opinions.

12. **Technical report diffing** — ChatGPT
    Upload 2022 vs 2025 feasibility — AI highlights only meaningful changes: capex +40%, IRR down, strip ratio up. Hasn't been done well anywhere.

13. **Red flags first (UX)** — Gemini
    Move red flags to the top of the report. Risks before upside. Simple change, immediate improvement.

14. **Permit & regulatory timeline tracker** — Gemini
    Extract environmental assessment, water license, and indigenous agreement milestones. Flag unexplained delays. Junior miners live and die by permits.

15. **Compliance / disclaimer architecture** — Fable
    As we add scores and recalculations we drift toward investment advice. Build disclaimer layer before launching to paying users.

---

## Tier 3 — Good ideas for later

16. **Management intelligence profiles** — ChatGPT, Opus
    Track records: mines built, exits, failures, dilution history, board overlaps across companies.

17. **Timeline mode** — ChatGPT
    Auto-extract development milestones over time (PEA → PFS → Feasibility → Permit → Construction). Show what changed at each stage.

18. **Mine economics benchmarking vs. peers** — ChatGPT
    "IRR 24% = top 20% among comparable Canadian open-pit gold projects." Requires building a project database over time.

19. **M&A comp benchmarking** — Fable
    "Developers in this jurisdiction have been acquired at $X–$Y/oz historically." More actionable than peer benchmarking.

20. **Dilution & insider transaction overlay chart** — Gemini
    Chart of share count over time with insider buy/sell transactions plotted on top. Visual, factual.

21. **Map integration** — Gemini
    Plot claim coordinates on a map alongside nearby producers and recent discoveries. Validates or challenges "nearology" claims.

22. **Lassonde curve positioning** — Opus
    Score each company against the standard mining lifecycle model. Shows where they sit and what the typical next catalyst is.

23. **"Five questions the expert would ask management"** — Fable
    Per company, generate the specific questions Rick Rule or Kevin McLean would ask. Great demo, directly uses our RAG.

24. **Clickable glossary** — ChatGPT
    Every technical term (NPV, strip ratio, AISC, inferred resource) is clickable. Expands to: what it is, why it matters, how it's manipulated.

25. **Cross-document Q&A** — ChatGPT
    "How many times has this company raised money in 5 years?" Synthesizes across all documents. Already partially built.

26. **Portfolio view** — Perplexity, ChatGPT
    Aggregate jurisdiction, commodity, and stage exposure across a user's holdings.

27. **Investment fit triage** — Perplexity
    On first use: explorer / developer / producer / royalty / turnaround? Tailor depth and framing.

28. **Drill hole data parsing** — Gemini
    Extract assay results from press releases. Compare gram-metre intercepts against historical and regional baselines.

29. **Missing diligence flagging** — Perplexity
    "No recent metallurgy update." "No sensitivity table." "No permitting discussion." Additive to existing red flags.

30. **Valuation lens modes** — Perplexity, Opus, Fable
    Let user pick interpretation mode: Rule contrarian, McLean NAV-focused, quality-focused. Uses existing RAG.

---

## Cross-cutting (strategic, not features)

- **The moat** (Opus, Fable): Standardization + Adversarial reading + External verification + Expert lens
- **Tagline**: "I checked whether the company's story survives contact with reality"
- **Depth vs. triage question** (Opus, Fable): Do users want to go deep on 1 stock or screen 40? Validate with 5 users before committing to a roadmap direction.
- **Workflow framing** (ChatGPT): Universe → Screen → Compare → Deep Dive → Monitor → Decision
