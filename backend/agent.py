import io
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pdfplumber
import requests as http
from supabase import create_client

from scraping import fetch_pdf_bytes, scrape_about_pages, scrape_news, discover_company

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
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
            timeout=120,
        )
        if response.ok:
            break
        if response.status_code == 429 and attempt < 2:
            wait = 20 * (attempt + 1)
            print(f"Gemini 429 rate limit (attempt {attempt+1}/3), waiting {wait}s...")
            time.sleep(wait)
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

## Recent Developments
Summarize the most significant news from the last 6 months. Focus on material events: permits, agreements, financings, drill results, project milestones. 3-5 bullet points. Note the date for each item.

## Company Snapshot
3-5 bullet points. What the company mines, where, and development stage (exploration / PEA / PFS / feasibility / production).

## Founders
Who founded the company, when, and a brief background on each founder. Note whether founders are still involved and in what capacity.

## Management Team
For EACH key executive and board member, write 4-5 lines covering: full name, title, total years of experience, key previous roles (specific company names and positions), and domain expertise. Use one sub-bullet per person.

## Insider Ownership & Compensation
From the Management Information Circular (proxy document):
- Total shares owned or controlled by all directors and officers combined, as a % of total shares outstanding.
- CEO shares owned or controlled specifically (number and %).
- CEO total annual compensation, broken down into each component: Base Salary, Annual Bonus, Share-Based Awards (RSUs/PSUs), Option-Based Awards, Pension Value, Any Other Compensation, and Total.
- If any component is nil or not applicable, state nil.
- If the Management Information Circular is not among the provided documents, write "Management Information Circular not provided — figures not available."

## Key Project Metrics
3-5 bullet points per project. Resource size, NPV (note whether pre-tax or after-tax), IRR, capex, mine life. Only include figures from the documents.

## Financials
3-5 bullet points. Cash position, shares outstanding, burn rate, recent financing activity.

## Jurisdiction
3-5 bullet points. Country/region of main projects, any sovereign risk factors mentioned in the documents.

## Red Flags
Work through EVERY item in the checklist below. For each one that applies, write a bullet with the specific factual observation. Then add any additional red flags you identify beyond this list.

CHECKLIST — check every item:

Technical Studies:
- Are any PEA, PFS, or feasibility studies older than 3 years? State the study name and its effective date.
- Are any Mineral Resource Estimates (MRE) older than 3 years? State the project name and effective date.
- Is any project still at PEA stage? (PEAs use inferred resources which are too speculative to be classified as mineral reserves.)

Valuation:
- Are NPV figures pre-tax or post-tax? Flag if pre-tax only.
- What gold/commodity price was assumed in the BASE CASE of each study? ONLY flag this if the base case assumed price is ABOVE the current gold price (which inflates the NPV). Ignore spot-price or sensitivity scenarios — only the base case assumption matters. If the base case price is below current gold price, skip this item entirely — do not mention it.
- Are government carried interests, royalties, and taxes fully netted out of the investor-level NPV, or is the NPV stated at project level only?

Dilution:
- Has the company completed private placements or public offerings in the last 3 years? List dates and amounts.
- Is the total share count growing year over year?
- Are there warrants or stock options outstanding that would further dilute shareholders?

Legal & Environmental:
- Any indigenous rights disputes, permit challenges, or court proceedings? State current status if known.
- Any legacy environmental liabilities (tailings, contamination, remediation obligations)? State amounts if disclosed.
- Any other ongoing litigation?

Financials:
- Is the current cash position disclosed? If yes, estimate runway based on burn rate. If not disclosed, flag it.
- Any significant debt or outstanding financial obligations?
- Compare current cash on hand to the total initial capex required for each project. State the gap explicitly and flag if the company has no disclosed plan (debt facility, strategic partner, streaming deal) to finance the difference.

Infrastructure:
- Is each project accessible by all-season road? If not, state the current access method and flag the infrastructure gap as a prerequisite for construction.

Jurisdiction:
- Are any projects located in high sovereign risk countries (outside Canada, Australia, USA, Scandinavia)?

Management:
- Any evidence of insider selling in the documents? (Insider buying is positive; omit if no data.)

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
- Plain English, short sentences."""


def _filter_docs(pdf_docs: dict[str, str]) -> dict[str, str]:
    """Keep only the most recent AIF and most recent MIC; skip older ones and ESTMA."""
    import re
    aif_pattern = re.compile(r"Annual Information Form.*?(\d{4})", re.IGNORECASE)
    mic_pattern = re.compile(r"(Management Information Circular|Information Circular).*?(\d{4})", re.IGNORECASE)
    skip_patterns = [re.compile(r"ESTMA", re.IGNORECASE)]

    def best_by_year(pattern, group):
        best_year, best_key = -1, None
        for label in pdf_docs:
            m = pattern.search(label)
            if m and int(m.group(group)) > best_year:
                best_year = int(m.group(group))
                best_key = label
        return best_key

    best_aif = best_by_year(aif_pattern, 1)
    best_mic = best_by_year(mic_pattern, 2)

    filtered = {}
    for label, url in pdf_docs.items():
        if any(p.search(label) for p in skip_patterns):
            continue
        if aif_pattern.search(label):
            if label == best_aif:
                filtered[label] = url
        elif mic_pattern.search(label):
            if label == best_mic:
                filtered[label] = url
        else:
            filtered[label] = url
    return filtered


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


def generate_overview(company_name: str, pdf_docs: dict[str, str], on_progress=None, dynamic_companies: dict | None = None) -> str:
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

    if not doc_texts:
        raise ValueError(f"Could not read any documents for {company_name}")

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
        "mining company NPV IRR capex management quality jurisdiction risk red flags investment analysis",
        match_count=8,
    )
    rag_context = ""
    if rag_chunks:
        rag_context = "EXPERT FRAMEWORKS (use as analytical lens, not as company facts):\n\n"
        for chunk in rag_chunks:
            rag_context += f"[{chunk['title']}]\n{chunk['content']}\n\n"
        rag_context += "\n"

    if on_progress:
        on_progress({"step": "generating", "label": "Generating overview with AI...", "current": 1, "total": 1})

    prompt = OVERVIEW_PROMPT.format(
        company_name=company_name,
        rag_context=rag_context,
        about_text=about_text or "Not available.",
        news_text=news_text,
        doc_texts="\n\n".join(doc_texts),
    )
    # Save the full assembled prompt so other LLMs can be tested on identical input
    import pathlib
    pathlib.Path(__file__).resolve().parent.joinpath("last_prompt.txt").write_text(
        prompt, encoding="utf-8"
    )
    history = [{"role": "user", "parts": [{"text": prompt}]}]
    return _call_gemini(history)


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
