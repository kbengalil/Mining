import io
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pdfplumber
import requests as http
from supabase import create_client

from scraping import fetch_pdf_bytes, scrape_about_pages, scrape_news, discover_company

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"

SYSTEM_INSTRUCTION = (
    "You are the Mining AI Analyst, a research assistant for junior mining stock analysis. "
    "You have access to investor documents provided by the user AND a knowledge base of expert frameworks "
    "from experienced resource investors like Rick Rule. "
    "When answering, draw on both sources. Be precise about what comes from the company documents "
    "versus what comes from expert knowledge. If a figure is not in the documents, say so rather than guessing."
)

# Full analyst prompt for later use:
# - Extract key metrics (NPV, IRR, capex/opex, resource category, study stage, mine life, ownership/dilution)
# - Cross-check promotional claims against the underlying figures in the same documents
# - Flag red flags: stale studies, partial-deposit valuations, cherry-picked price decks, undisclosed dilution risk
# - Explain mining and financial terminology in plain language for a non-expert investor

chat_sessions: dict[str, list] = {}

_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    return _supabase


def _extract_text(pdf_bytes: bytes) -> str:
    # EDGAR files come as HTML — detect and handle them directly
    sample = pdf_bytes[:500].lstrip()
    if sample.startswith(b"<") or b"<!DOCTYPE" in sample[:100]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(pdf_bytes, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _embed_query(text: str) -> list[float]:
    key = os.environ["GEMINI_API_KEY"]
    resp = http.post(
        f"{EMBED_URL}?key={key}",
        headers={"Content-Type": "application/json"},
        json={"content": {"parts": [{"text": text}]}, "outputDimensionality": 768},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def _search_rag(query: str, match_count: int = 5) -> list[dict]:
    try:
        vector = _embed_query(query)
        result = _get_supabase().rpc("match_knowledge_base", {
            "query_embedding": vector,
            "match_count": match_count,
        }).execute()
        return result.data or []
    except Exception as e:
        print(f"RAG search failed: {e}")
        return []


def _call_gemini(history: list) -> str:
    key = os.environ["GEMINI_API_KEY"]
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": history,
    }
    for attempt in range(3):
        response = http.post(
            GEMINI_URL,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=payload,
            timeout=1000,
        )
        if response.ok:
            break
        if response.status_code == 429:
            if attempt < 2:
                wait = 20 * (attempt + 1)
                print(f"Gemini 429 rate limit (attempt {attempt+1}/3), waiting {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError("Gemini API quota exceeded. Please try again later or check your billing quota.")
        else:
            response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


OVERVIEW_PROMPT = """You are the Mining AI Analyst. Produce a structured company overview for {company_name} using the investor documents, company website, recent news, and expert frameworks below.

{rag_context}
COMPANY WEBSITE (management & about pages):
{about_text}

RECENT NEWS (newest first):
{news_text}

COMPANY DOCUMENTS:
{doc_texts}

Write EXACTLY these 9 sections with markdown headers. Be concise and factual.

## The Team

### Founders
Who founded the company, when, and a brief background on each founder. Note whether founders are still involved and in what capacity.

### Management Team
For EACH key executive and board member, write 4-5 lines covering: full name, title, total years of experience, key previous roles (specific company names and positions), and domain expertise. Use one sub-bullet per person.

### Insider Ownership & Compensation
From the Management Information Circular (proxy document):
- Total shares owned or controlled by all directors and officers combined, as a % of total shares outstanding.
- CEO shares owned or controlled specifically (number and %).
- CEO total annual compensation, broken down into each component: Base Salary, Annual Bonus, Share-Based Awards (RSUs/PSUs), Option-Based Awards, Pension Value, Any Other Compensation, and Total.
- If any component is nil or not applicable, state nil.
- If the Management Information Circular is not among the provided documents, write "Management Information Circular not provided — figures not available."
Also check presentations and fact sheets for major strategic shareholders (individuals or institutions owning >5%): list each name, approximate % ownership, and any notable detail (e.g. converted debt to equity, long-term holder, founding investor).

## Company Snapshot
3-5 bullet points. What the company mines, where, and development stage (exploration / PEA / PFS / feasibility / production).

## Key Project Metrics
For EACH project, extract ALL of the following that are disclosed — do not skip any:
- Resource: tonnes, grade, contained metal (state M&I and Inferred separately)
- Reserves: tonnes, grade, contained metal (if stated)
- NPV: amount, discount rate, commodity price assumed, pre-tax or post-tax
- IRR: % and commodity price assumed
- Initial capex
- Mine life
- Average annual production (state the period, e.g. years 1-5 vs LOM)
- Exploration upside (open along strike/depth, new zones, % of trend tested)
Include growth projects from any announced mergers or acquisitions — label them clearly as "(from pending acquisition of [company])".

## Financials
Extract ALL of the following that are disclosed — do not summarize or skip:
- Cash on hand (state the date of the figure)
- Total debt — broken down long-term vs short-term (state the date)
- Net debt — total debt minus cash on hand (calculate explicitly)
- Available liquidity — cash plus undrawn credit facilities (state facility name, total size, amount drawn, amount undrawn)
- Shares outstanding (state the date)
- Warrants outstanding (number and expiry/strike if disclosed)
- Options/RSUs/PSUs/DSUs outstanding (totals)
- Cash burn rate (total cash used in operating activities per year, for each year disclosed in the financials)
- EVERY financing event in the documents: date, type (private placement / public offering / flow-through / warrant exercise), amount raised, shares issued, warrant coverage if any
- Projected annual cash flow or net free cash flow (LOM or annual, if disclosed)
- Any stated annual exploration or capital spending budget

## Jurisdiction
3-5 bullet points. Country/region of main projects, any sovereign risk factors mentioned in the documents.

## Recent Developments
List EVERY material news item from the last 6 months found in the documents or recent news feed. Include all of: permits, agreements, financings, drill results, project milestones, legal updates, partnerships. One bullet per event, with the exact date. Do not summarize multiple events into one bullet.

## Valuation vs Peers
If the documents include any peer group comparison: state the company's P/NAV (or EV/NAV or P/CF), the peer group median for the same metric, and the implied discount or premium. List the peer companies named. If no peer comparison is in the documents, write "Not disclosed."

## Strategic Outlook
Summarize explicit management statements from any document on: future M&A appetite (e.g. "no further acquisitions planned"), annual exploration or capital spending targets ($X/year), production growth timeline and targets, dividend or buyback policy, and any other stated priorities. Quote figures directly where available. If not disclosed, write "Not disclosed."

## Red Flags
Work through EVERY item in the checklist below. For each one that applies, write a bullet with the specific factual observation. Then add any additional red flags you identify beyond this list.

CHECKLIST — check every item:

Technical Studies:
- Are any PEA, PFS, or feasibility studies older than 3 years? State the study name and its effective date.
- Are any Mineral Resource Estimates (MRE) older than 3 years? State the project name and effective date.
- Is any project still at PEA stage? (PEAs use inferred resources which are too speculative to be classified as mineral reserves.)

Valuation:
- Are NPV figures pre-tax or post-tax? Flag if pre-tax only.
- Are government carried interests, royalties, and taxes fully netted out of the investor-level NPV, or is the NPV stated at project level only?

Dilution:
- Has the company completed private placements or public offerings in the last 3 years? List dates and amounts.
- Is the total share count growing year over year?
- Are there warrants or stock options outstanding that would further dilute shareholders?
- Were recent financings done with warrant coverage? State the warrant ratio (e.g. half-warrant, full warrant) and strike price for each. A financing done with full warrant coverage at a deep discount to market is a red flag — it signals weak demand and hands investors cheap optionality at existing shareholders' expense.
- Has the company raised money when its stock was near multi-year lows with heavy warrant coverage? Repeated distress financings ruin the capital structure and trap the stock.

Legal & Environmental:
- Any indigenous rights disputes, permit challenges, or court proceedings? State current status if known.
- Any legacy environmental liabilities (tailings, contamination, remediation obligations)? State amounts if disclosed.
- Any other ongoing litigation?

Financials:
- Is the current cash position disclosed? If not disclosed, flag it.
  - If the company is in EXPLORATION stage (no construction decision made, no project financing arranged): divide cash on hand by the most recent annual cash burn rate (cash used in operating activities) to estimate runway in months. State the calculation explicitly.
  - If the company is in DEVELOPMENT or CONSTRUCTION stage (feasibility complete, project financing arranged, or construction decision announced): do NOT calculate exploration runway — it is misleading. Instead, state total disclosed capex budget vs. total disclosed funding (cash + debt facilities + streaming proceeds + any other committed capital). Flag any funding gap. If construction is paused (permitting, security, or other reasons), state the estimated monthly holding cost (desktop/engineering work only) and how long current cash covers that rate.
- Any significant debt or outstanding financial obligations?
- Compare current cash on hand to the total initial capex required for each project. State the gap explicitly and flag if the company has no disclosed plan (debt facility, strategic partner, streaming deal) to finance the difference.

Infrastructure:
- Is each project accessible by all-season road? If not, state the current access method and flag the infrastructure gap as a prerequisite for construction.

Jurisdiction:
- Are any projects located in high sovereign risk countries (outside Canada, Australia, USA, Scandinavia)?

Management:
- Any evidence of insider selling in the documents? (Insider buying is positive; omit if no data.)
- Is the total CEO/NEO compensation high relative to the company's stage? For a pre-revenue junior with no commercial production, a CEO base salary above $500K is a potential alignment concern. State the actual figures from the MIC.
- Are key decision-makers (chairman, CEO) receiving salary AND options AND share-based awards simultaneously while the company has not yet produced metal? Flag if total package appears disproportionate to company progress.
- Do any directors or officers hold their position without owning a meaningful stake in the company? Low or zero insider ownership at the board level is a misalignment signal.

Business Stage:
- Has the company ever produced metal commercially? If not, state this explicitly.
- Is the company entirely dependent on equity financing to fund operations? If so, state the implication: the company must continuously issue shares (diluting existing shareholders) to survive.
- Are there any streaming or royalty agreements that reduce the company's share of future revenue? List each stream: commodity, percentage sold, payment terms, and counterparty.

After completing the checklist, add any additional red flags you identify that are not covered above.
Cross-reference with Recent News: if a red flag from the documents has been resolved in a recent press release, keep the bullet but append "— Resolved per [date] press release."
Omit any checklist item where there is genuinely nothing to flag — do not write "no issues found" for clean items.

RULES:
- Do not invent data. If something is not in the documents or website, write "Not disclosed."
- No investment advice. No buy/sell/hold language. No verdicts or opinions.
- Red flags are factual observations, not judgments.
- Plain English, short sentences.
- When two documents conflict on the same fact, always use the MORE RECENT document. If the conflict is material (e.g. a legal dispute shown as unresolved in an older doc but resolved in a newer one), note both versions and cite the dates."""


def _filter_docs(pdf_docs: dict[str, str]) -> dict[str, str]:
    import re
    from datetime import date, timedelta

    # Labels to drop unconditionally (case-insensitive exact match)
    SKIP_EXACT = {
        "learn more", "articles", "english", "spanish", "englis", "slides",
        "transcript", "presentation", "fact sheet", "press release",
        "management approach", "sustainability management approach",
        "report on the implementation of the responsible gold mining principles",
        "report on the implementation of the conflict-free gold standard",
    }

    # Labels to drop if the pattern appears anywhere in the label
    # Note: \b word boundaries fail next to underscores (underscore is a word char),
    # so use (?<![a-zA-Z]) / (?![a-zA-Z]) instead for labels like SEDAR_Proxy_English.
    SKIP_RE = [
        re.compile(r"(?<![a-zA-Z])estma(?![a-zA-Z])", re.IGNORECASE),
        re.compile(r"test[_\-]?pdf", re.IGNORECASE),
        re.compile(r"forced labour", re.IGNORECASE),
        re.compile(r"voluntary carbon", re.IGNORECASE),
        re.compile(r"supply chain", re.IGNORECASE),
        re.compile(r"(?<![a-zA-Z])proxy(?![a-zA-Z])", re.IGNORECASE),
        re.compile(r"(?<![a-zA-Z])vif(?![a-zA-Z])|voting instruction", re.IGNORECASE),
        re.compile(r"request[\s_]form", re.IGNORECASE),
        re.compile(r"notice[\s_]of[\s_](?:\w+[\s_])*meeting", re.IGNORECASE),
        re.compile(r"sedar[_\s-]+notice", re.IGNORECASE),
        re.compile(r"notice[\s_]of[\s_]availability", re.IGNORECASE),
    ]

    # Financial docs older than 4 years: FS, MD&A, quarterly/annual financials
    FINANCIAL_KEYWORDS_RE = re.compile(
        r"\b(?:fs|mda|md&a|financial|financials|statements?|quarterly|interim)\b",
        re.IGNORECASE,
    )
    YEAR_IN_LABEL_RE = re.compile(r"(20\d{2})")

    AIF_RE = re.compile(r"annual information form.*?(\d{4})", re.IGNORECASE)
    MIC_RE = re.compile(r"(management information circular|information circular).*?(\d{4})", re.IGNORECASE)

    # Press release: label starts with "Month D(D), YYYY"
    _MONTH_MAP = {m: i + 1 for i, m in enumerate(
        "january february march april may june july august september october november december".split()
    )}
    PR_RE = re.compile(
        r"^(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+(\d{1,2}),\s+(\d{4})\b",
        re.IGNORECASE,
    )

    # Dated ESG/Sustainability docs: "2021 ESG Report", "2022 Sustainability Report", etc.
    DATED_ESG_RE = re.compile(
        r"^(20\d{2})\s+.*(esg|sustainability|climate|water|tailings)",
        re.IGNORECASE,
    )

    today = date.today()
    six_months_ago = today - timedelta(days=183)

    def best_by_year(pattern, group):
        best_year, best_key = -1, None
        for label in pdf_docs:
            m = pattern.search(label)
            if m and int(m.group(group)) > best_year:
                best_year = int(m.group(group))
                best_key = label
        return best_key

    best_aif = best_by_year(AIF_RE, 1)
    best_mic = best_by_year(MIC_RE, 2)

    # Generic FS/MD&A labels (e.g. "FS", "FS (2)", "MD&A (3)") — no date in label, check URL
    GENERIC_FIN_RE = re.compile(
        r"^(?:fs|md&a|mda|financial\s+reports?|financial\s+statements?)(?:\s*\(\d+\))?$",
        re.IGNORECASE,
    )
    fin_counts = {"fs": 0, "mda": 0}
    MAX_FIN_DOCS = 6

    press_releases = []  # (date, label, url)
    regular = {}

    for label, url in pdf_docs.items():
        s = label.strip()

        if len(s) < 4:
            continue
        if s.lower() in SKIP_EXACT:
            continue
        if any(p.search(s) for p in SKIP_RE):
            continue

        # AIF: keep only most recent
        if AIF_RE.search(s):
            if s == best_aif:
                regular[s] = url
            continue

        # MIC: keep only most recent
        if MIC_RE.search(s):
            if s == best_mic:
                regular[s] = url
            continue

        # Press release: collect for date-based filtering below
        m = PR_RE.match(s)
        if m:
            month_num = _MONTH_MAP[m.group(1).lower()]
            try:
                pr_date = date(int(m.group(3)), month_num, int(m.group(2)))
                press_releases.append((pr_date, s, url))
            except ValueError:
                pass
            continue

        # Dated ESG docs: skip if older than 2 years
        m_esg = DATED_ESG_RE.match(s)
        if m_esg:
            if int(m_esg.group(1)) >= today.year - 2:
                regular[s] = url
            continue

        # General year filter: drop any doc with a year older than 2 years in its label.
        # Exception: technical reports (NI 43-101) may be the only resource estimate available.
        years_in_label = [int(y) for y in YEAR_IN_LABEL_RE.findall(s)]
        if years_in_label and max(years_in_label) < today.year - 2:
            if not re.search(r"technical[\s_]report|ni[\s_]*43[-\s]101", s, re.IGNORECASE):
                continue

        # Generic FS/MD&A labels: check URL for year and cap at MAX_FIN_DOCS each
        if GENERIC_FIN_RE.match(s):
            url_years = [int(y) for y in YEAR_IN_LABEL_RE.findall(url)]
            if url_years and max(url_years) < today.year - 2:
                continue
            bucket = "mda" if re.search(r"md&?a", s, re.IGNORECASE) else "fs"
            if fin_counts[bucket] >= MAX_FIN_DOCS:
                continue
            fin_counts[bucket] += 1

        regular[s] = url

    # Press releases: keep last 6 months; if fewer than 5, take the 5 most recent
    press_releases.sort(key=lambda x: x[0], reverse=True)
    recent_prs = [(lbl, url) for d, lbl, url in press_releases if d >= six_months_ago]
    if len(recent_prs) < 5:
        recent_prs = [(lbl, url) for _, lbl, url in press_releases[:5]]
    for lbl, url in recent_prs:
        regular[lbl] = url

    return regular


def detect_company_intent(message: str) -> str | None:
    """Return the mining company name if the user wants an analysis, else None."""
    key = os.environ["GEMINI_API_KEY"]
    prompt = f"""A user sent this message to a mining stock analysis chatbot:

"{message}"

If the user is asking to analyze, research, scan, review, check, or get information about a specific mining company, return ONLY the company name exactly as the user wrote it.
If the message is a general question, greeting, or anything other than a request to analyze a specific company, return ONLY the word "none".

Examples:
"analyze First Mining Gold" → First Mining Gold
"can you look at Osisko Mining for me?" → Osisko Mining
"what do you think about Agnico Eagle?" → Agnico Eagle
"run a scan on Endeavour Silver" → Endeavour Silver
"i want to see a report on Torex Gold" → Torex Gold
"check out MAG Silver for me" → MAG Silver
"what is NAV?" → none
"how does the silver stream work?" → none
"hello" → none

Return ONLY the company name or the word none."""

    resp = http.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
        timeout=15,
    )
    if not resp.ok:
        return None
    result = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    return None if result.lower() == "none" else result


def _read_one_pdf(args):
    label, url = args
    try:
        return label, _extract_text(fetch_pdf_bytes(url)), None
    except Exception as e:
        return label, None, str(e)


def generate_overview(company_name: str, pdf_docs: dict[str, str], on_progress=None, dynamic_companies: dict | None = None, skip_filter: bool = False) -> str:
    if not skip_filter:
        pdf_docs = _filter_docs(pdf_docs)
    total = len(pdf_docs)
    completed = 0
    raw_results = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_read_one_pdf, (label, url)): label for label, url in pdf_docs.items()}
        for future in as_completed(futures):
            label, text, error = future.result()
            completed += 1
            if on_progress:
                on_progress({"step": "reading", "label": f"Reading: {label}", "current": completed, "total": total})
            if text:
                raw_results[label] = text
            else:
                print(f"  Skipping {label}: {error}")

    # Deduplicate by content fingerprint
    seen_hashes = set()
    doc_texts = []
    for label in pdf_docs:  # preserve original order
        text = raw_results.get(label)
        if not text:
            continue
        fingerprint = text[:500]
        if fingerprint in seen_hashes:
            continue
        seen_hashes.add(fingerprint)
        doc_texts.append(f"--- {label} ---\n{text}")

    no_docs = not doc_texts

    if on_progress:
        on_progress({"step": "scraping", "label": "Scraping company website...", "current": 1, "total": 1})
    about_text = scrape_about_pages(company_name, dynamic_companies)

    if on_progress:
        on_progress({"step": "news", "label": "Fetching recent news...", "current": 1, "total": 1})
    news_items = scrape_news(company_name, dynamic_companies=dynamic_companies)
    if news_items:
        news_text = "\n".join(f"- {i['date_str']}: {i['headline']}" for i in news_items)
    else:
        news_text = "No recent news found."

    if on_progress:
        on_progress({"step": "rag", "label": "Searching expert knowledge base...", "current": 1, "total": 1})
    rag_chunks = _search_rag(
        "mining company NPV IRR capex management quality jurisdiction risk red flags investment analysis "
        "insider ownership compensation alignment warrant financing dilution capital structure M&A",
        match_count=10,
    )
    rag_context = ""
    if rag_chunks:
        rag_context = "EXPERT FRAMEWORKS (use as analytical lens, not as company facts):\n\n"
        for chunk in rag_chunks:
            rag_context += f"[{chunk['title']}]\n{chunk['content']}\n\n"
        rag_context += "\n"

    if on_progress:
        on_progress({"step": "generating", "label": "Generating overview with AI...", "current": 1, "total": 1})

    no_docs_notice = ""
    if no_docs:
        no_docs_notice = (
            "⚠️ IMPORTANT: No investor documents could be fetched automatically for this company "
            "(financial statements, MD&A, AIF, technical reports). "
            "The report below is based ONLY on the company website and recent news. "
            "Financial figures, resource estimates, NPV/IRR, and cash position are NOT available. "
            "Skip any section that requires document data — do not guess or fabricate numbers. "
            "For a full report, the user should paste direct PDF links into the chat.\n\n"
        )

    prompt = OVERVIEW_PROMPT.format(
        company_name=company_name,
        rag_context=rag_context,
        about_text=about_text or "Not available.",
        news_text=news_text,
        doc_texts=no_docs_notice + ("\n\n".join(doc_texts) if doc_texts else "No documents available."),
    )
    # Save the full assembled prompt so other LLMs can be tested on identical input
    import pathlib
    pathlib.Path(__file__).resolve().parent.joinpath("last_prompt.txt").write_text(
        prompt, encoding="utf-8"
    )
    history = [{"role": "user", "parts": [{"text": prompt}]}]
    report = _call_gemini(history)

    if no_docs:
        report = (
            "## ⚠️ Partial Report — Documents Not Available\n"
            "We were unable to automatically fetch financial documents (AIF, financial statements, MD&A, technical reports) for this company. "
            "This report is based on the company website and recent news only. "
            "Financial figures, resource estimates, and NPV/IRR are not available.\n\n"
            "**To get a full report:** paste direct PDF links (from the company website or SEDAR) into the chat.\n\n"
            "---\n\n"
        ) + report

    return report


def send_message_with_overview(message: str, overview_md: str, company_name: str, session_id: str | None) -> tuple[str, str]:
    """Answer a question using a pre-loaded company overview as context."""
    if session_id is None or session_id not in chat_sessions:
        session_id = str(uuid.uuid4())
        chat_sessions[session_id] = []
        context = f"Here is the research report for {company_name}:\n\n{overview_md}"
        chat_sessions[session_id].append({"role": "user", "parts": [{"text": context}]})
        chat_sessions[session_id].append({"role": "model", "parts": [{"text": f"I have the research report for {company_name}. What would you like to know?"}]})

    rag_chunks = _search_rag(message)
    if rag_chunks:
        rag_context = "Relevant expert knowledge:\n\n"
        for chunk in rag_chunks:
            rag_context += f"[{chunk['title']}]\n{chunk['content']}\n\n"
        augmented_message = f"{rag_context}---\n\nUser question: {message}"
    else:
        augmented_message = message

    history = chat_sessions[session_id]
    history.append({"role": "user", "parts": [{"text": augmented_message}]})
    reply = _call_gemini(history)
    history[-1] = {"role": "user", "parts": [{"text": message}]}
    history.append({"role": "model", "parts": [{"text": reply}]})
    return reply, session_id


def send_message(message: str, documents: dict[str, str], session_id: str | None) -> tuple[str, str]:
    if session_id is None or session_id not in chat_sessions:
        session_id = str(uuid.uuid4())
        chat_sessions[session_id] = []

        if documents:
            doc_texts = []
            for label, url in documents.items():
                try:
                    text = _extract_text(fetch_pdf_bytes(url))
                    doc_texts.append(f"--- {label} ---\n{text}")
                except Exception:
                    continue
            if doc_texts:
                context = "Here are the investor documents provided for analysis:\n\n" + "\n\n".join(doc_texts)
                chat_sessions[session_id].append(
                    {"role": "user", "parts": [{"text": context}]}
                )
                chat_sessions[session_id].append(
                    {"role": "model", "parts": [{"text": "I have read the documents. What would you like to know?"}]}
                )

    # Search RAG for relevant expert knowledge on each message
    rag_chunks = _search_rag(message)
    if rag_chunks:
        rag_context = "Relevant expert knowledge:\n\n"
        for chunk in rag_chunks:
            rag_context += f"[{chunk['title']}]\n{chunk['content']}\n\n"
        augmented_message = f"{rag_context}---\n\nUser question: {message}"
    else:
        augmented_message = message

    # Send augmented message to Gemini but store only the clean message in history
    history = chat_sessions[session_id]
    history.append({"role": "user", "parts": [{"text": augmented_message}]})
    reply = _call_gemini(history)
    # Replace stored message with clean version to keep history compact
    history[-1] = {"role": "user", "parts": [{"text": message}]}
    history.append({"role": "model", "parts": [{"text": reply}]})

    return reply, session_id
