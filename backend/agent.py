import io
import os

import pdfplumber
import requests as http

from scraping import fetch_pdf_bytes

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_INSTRUCTION = "You are the Mining AI Analyst, a research assistant for junior mining stock analysis."

# Full analyst prompt for later use:
# Given investor documents (decks, financials, technical reports) for a company, you:
# - Extract key metrics (NPV, IRR, capex/opex, resource category, study stage, mine life, ownership/dilution)
# - Cross-check promotional claims against the underlying figures in the same documents
# - Flag red flags: stale studies, partial-deposit valuations, cherry-picked price decks, undisclosed dilution risk
# - Explain mining and financial terminology in plain language for a non-expert investor
# Be precise about what is stated in the documents versus what you infer. If a figure is not in the provided documents, say so rather than guessing.

# In-memory chat sessions: {session_id: [{"role": ..., "parts": [{"text": ...}]}, ...]}
chat_sessions: dict[str, list] = {}


def _extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _call_gemini(history: list) -> str:
    key = os.environ["GEMINI_API_KEY"]
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": history,
    }
    response = http.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def send_message(message: str, documents: dict[str, str], session_id: str | None) -> tuple[str, str]:
    import uuid

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

    history = chat_sessions[session_id]
    history.append({"role": "user", "parts": [{"text": message}]})

    reply = _call_gemini(history)

    history.append({"role": "model", "parts": [{"text": reply}]})
    return reply, session_id
