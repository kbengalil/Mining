import io
import os
import time
import uuid

import pdfplumber
import requests as http
from supabase import create_client

from scraping import fetch_pdf_bytes, scrape_about_pages

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


OVERVIEW_PROMPT = """You are the Mining AI Analyst. Produce a structured company overview for {company_name} using the investor documents, company website, and expert frameworks below.

{rag_context}
COMPANY WEBSITE (management & about pages):
{about_text}

COMPANY DOCUMENTS:
{doc_texts}

Write EXACTLY these 7 sections with markdown headers. Be concise and factual.

## Company Snapshot
3-5 bullet points. What the company mines, where, and development stage (exploration / PEA / PFS / feasibility / production).

## Founders
Who founded the company, when, and a brief background on each founder. Note whether founders are still involved and in what capacity.

## Management Team
For EACH key executive and board member, write 4-5 lines covering: full name, title, total years of experience, key previous roles (specific company names and positions), and domain expertise. Use one sub-bullet per person.

## Key Project Metrics
3-5 bullet points per project. Resource size, NPV (note whether pre-tax or after-tax), IRR, capex, mine life. Only include figures from the documents.

## Financials
3-5 bullet points. Cash position, shares outstanding, burn rate, recent financing activity.

## Jurisdiction
3-5 bullet points. Country/region of main projects, any sovereign risk factors mentioned in the documents.

## Red Flags
Factual observations only. Examples: "NPV figures are pre-tax only", "last technical study published in 2019", "cash position not disclosed in most recent filing". Omit bullets that do not apply.

RULES:
- Do not invent data. If something is not in the documents or website, write "Not disclosed."
- No investment advice. No buy/sell/hold language. No verdicts or opinions.
- Red flags are factual observations, not judgments.
- Plain English, short sentences."""


def _filter_docs(pdf_docs: dict[str, str]) -> dict[str, str]:
    """Keep only the most recent AIF; skip older AIFs and ESTMA."""
    import re
    aif_pattern = re.compile(r"Annual Information Form.*?(\d{4})", re.IGNORECASE)
    skip_patterns = [re.compile(r"ESTMA", re.IGNORECASE)]

    best_aif_year = -1
    best_aif_key = None
    for label in pdf_docs:
        m = aif_pattern.search(label)
        if m and int(m.group(1)) > best_aif_year:
            best_aif_year = int(m.group(1))
            best_aif_key = label

    filtered = {}
    for label, url in pdf_docs.items():
        if any(p.search(label) for p in skip_patterns):
            continue
        if aif_pattern.search(label):
            if label == best_aif_key:
                filtered[label] = url
        else:
            filtered[label] = url
    return filtered


def generate_overview(company_name: str, pdf_docs: dict[str, str], on_progress=None) -> str:
    pdf_docs = _filter_docs(pdf_docs)
    total = len(pdf_docs)
    seen_hashes = set()
    doc_texts = []

    for i, (label, url) in enumerate(pdf_docs.items(), 1):
        if on_progress:
            on_progress({"step": "reading", "label": f"Reading: {label}", "current": i, "total": total})
        try:
            text = _extract_text(fetch_pdf_bytes(url))
            # Skip duplicate documents (same content, different label)
            fingerprint = text[:500]
            if fingerprint in seen_hashes:
                continue
            seen_hashes.add(fingerprint)
            doc_texts.append(f"--- {label} ---\n{text}")
        except Exception as e:
            print(f"  Skipping {label}: {e}")

    if not doc_texts:
        raise ValueError(f"Could not read any documents for {company_name}")

    if on_progress:
        on_progress({"step": "scraping", "label": "Scraping company website...", "current": 1, "total": 1})
    about_text = scrape_about_pages(company_name)

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
        doc_texts="\n\n".join(doc_texts),
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
