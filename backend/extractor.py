"""
Structured fact extraction from mining company documents.
Reads PDFs, classifies them by document type, extracts key metrics via Gemini,
and stores results in Supabase fact tables.

Called automatically from run_overview_job() in main.py after every report.
Uses the UNFILTERED pdf_docs so proxy documents are included even though
_filter_docs() in agent.py excludes them from the report prompt.
"""

import io
import json
import os
import re
from datetime import datetime, timezone

import pdfplumber
import requests as http
from supabase import create_client

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    return _supabase


# ── Document type → Supabase table ──────────────────────────────────────────

TABLE_FOR_TYPE = {
    "ni_43101":     "ni_43101_facts",
    "financial":    "financial_facts",
    "mda":          "mda_facts",
    "press_release":"press_release_facts",
    "presentation": "presentation_facts",
    "proxy":        "proxy_facts",
}

# ── Fields per table — used for null report ──────────────────────────────────

TABLE_FIELDS = {
    "ni_43101_facts": [
        "study_type", "resource_tonnage", "resource_grade", "resource_classification",
        "npv", "npv_discount_rate", "irr", "capex_initial", "opex_per_tonne",
        "strip_ratio", "metallurgical_recovery", "mine_life_years",
        "qp_name", "report_date", "metal_price_assumption",
    ],
    "financial_facts": [
        "cash_and_equivalents", "total_debt", "working_capital",
        "shares_basic", "shares_diluted", "mineral_property_book_value",
        "going_concern", "auditor", "fiscal_year_end",
        "annual_revenue", "royalty_obligations", "streaming_agreements",
    ],
    "mda_facts": [
        "aisc", "cash_cost", "production_guidance", "quarterly_cash_burn",
        "cash_runway_months", "key_risks", "liquidity_outlook",
    ],
    "press_release_facts": [
        "drill_intercept_best", "grade_thickness_score", "financing_type",
        "financing_amount", "dilution_shares_issued", "permits_received",
        "management_changes", "ma_activity", "resource_update",
    ],
    "presentation_facts": [
        "primary_commodity", "development_stage", "upcoming_catalysts",
        "jurisdiction", "insider_ownership_pct", "market_cap", "enterprise_value",
    ],
    "proxy_facts": [
        "ceo_total_compensation", "ceo_base_salary", "ceo_shares_owned",
        "board_size", "independent_directors_count", "related_party_transactions",
        "say_on_pay_vote_pct", "total_insider_ownership_pct",
    ],
}

# ── Document classification ───────────────────────────────────────────────────

_MONTH_NAMES = "january|february|march|april|may|june|july|august|september|october|november|december"

# Order matters: more specific patterns first
_CLASSIFY_PATTERNS = [
    ("ni_43101",      re.compile(r"technical[\s_]report|ni[\s_]*43[-\s]101|sk[-\s]?1300|43101", re.IGNORECASE)),
    ("proxy",         re.compile(r"(?<![a-zA-Z])proxy(?![a-zA-Z])|management\s+information\s+circular|(?<![a-zA-Z])mic(?![a-zA-Z])\b", re.IGNORECASE)),
    ("mda",           re.compile(r"md&?a|management['\s]+discussion", re.IGNORECASE)),
    ("financial",     re.compile(r"financial[\s_]statement|annual[\s_]report|(?<![a-zA-Z])(?:fs|aif)(?![a-zA-Z])|annual[\s_]information[\s_]form", re.IGNORECASE)),
    ("press_release", re.compile(rf"^(?:{_MONTH_NAMES})\s+\d{{1,2}},\s+\d{{4}}", re.IGNORECASE)),
    ("press_release", re.compile(r"^nr-\d{8}", re.IGNORECASE)),
    ("presentation",  re.compile(r"presentation|investor[\s_]deck|corporate[\s_]deck|fact[\s_]sheet", re.IGNORECASE)),
]


def classify_document(label: str) -> str | None:
    for doc_type, pattern in _CLASSIFY_PATTERNS:
        if pattern.search(label):
            return doc_type
    return None


# ── Extraction prompts ────────────────────────────────────────────────────────

EXTRACTION_PROMPTS = {
    "ni_43101": (
        "You are a mining analyst. Extract the following fields from this NI 43-101 Technical Report. "
        "Return ONLY a valid JSON object — no markdown, no explanation. Use null for any field not found.\n\n"
        '{\n'
        '  "study_type": "one of: PEA, PFS, FS, or null",\n'
        '  "resource_tonnage": "e.g. \'50 Mt\' or null",\n'
        '  "resource_grade": "e.g. \'4.2 g/t Au\' or null",\n'
        '  "resource_classification": "e.g. \'60% Indicated, 40% Inferred\' or null",\n'
        '  "npv": "e.g. \'US$380M\' or null",\n'
        '  "npv_discount_rate": "e.g. \'5%\' or null",\n'
        '  "irr": "e.g. \'28%\' or null",\n'
        '  "capex_initial": "e.g. \'US$238.7M\' or null",\n'
        '  "opex_per_tonne": "e.g. \'US$12.50/t\' or null",\n'
        '  "strip_ratio": "e.g. \'3.5:1\' or null",\n'
        '  "metallurgical_recovery": "e.g. \'92%\' or null",\n'
        '  "mine_life_years": "e.g. \'12\' or null",\n'
        '  "qp_name": "e.g. \'John Smith, P.Geo\' or null",\n'
        '  "report_date": "e.g. \'March 2025\' or null",\n'
        '  "metal_price_assumption": "e.g. \'Gold US$1,800/oz\' or null"\n'
        '}\n\nDocument text (first 50,000 characters):\n'
    ),
    "financial": (
        "You are a mining analyst. Extract the following fields from this Annual Report, Financial Statements, or AIF. "
        "Return ONLY a valid JSON object — no markdown, no explanation. Use null for any field not found.\n\n"
        '{\n'
        '  "cash_and_equivalents": "e.g. \'US$59M as at March 31 2026\' or null",\n'
        '  "total_debt": "e.g. \'US$239M (US$200M long-term, US$39M short-term)\' or null",\n'
        '  "working_capital": "e.g. \'US$45M\' or null",\n'
        '  "shares_basic": "e.g. \'180M\' or null",\n'
        '  "shares_diluted": "e.g. \'210M\' or null",\n'
        '  "mineral_property_book_value": "e.g. \'US$320M\' or null",\n'
        '  "going_concern": "true if going concern note exists, false if not, null if unclear",\n'
        '  "auditor": "e.g. \'Deloitte\' or null",\n'
        '  "fiscal_year_end": "e.g. \'December 31\' or null",\n'
        '  "annual_revenue": "e.g. \'US$120M\' or null",\n'
        '  "royalty_obligations": "e.g. \'2% NSR to Franco-Nevada\' or null",\n'
        '  "streaming_agreements": "e.g. \'20% silver stream to Wheaton\' or null"\n'
        '}\n\nDocument text (first 50,000 characters):\n'
    ),
    "mda": (
        "You are a mining analyst. Extract the following fields from this MD&A. "
        "Return ONLY a valid JSON object — no markdown, no explanation. Use null for any field not found.\n\n"
        '{\n'
        '  "aisc": "all-in sustaining cost e.g. \'US$1,050/oz\' or null",\n'
        '  "cash_cost": "e.g. \'US$850/oz\' or null",\n'
        '  "production_guidance": "e.g. \'120,000-130,000 oz Au\' or null",\n'
        '  "quarterly_cash_burn": "e.g. \'US$8M/quarter\' or null",\n'
        '  "cash_runway_months": "e.g. \'7 months\' or null",\n'
        '  "key_risks": "e.g. \'Permitting delay, FX exposure\' or null",\n'
        '  "liquidity_outlook": "one of: Adequate, At risk, or null"\n'
        '}\n\nDocument text (first 50,000 characters):\n'
    ),
    "press_release": (
        "You are a mining analyst. Extract the following fields from this press release. "
        "Return ONLY a valid JSON object — no markdown, no explanation. Use null for any field not found.\n\n"
        '{\n'
        '  "drill_intercept_best": "best drill intercept e.g. \'50m at 4.2 g/t Au\' or null",\n'
        '  "grade_thickness_score": "width × grade as a number e.g. 210 or null",\n'
        '  "financing_type": "e.g. \'Bought deal\' or null",\n'
        '  "financing_amount": "e.g. \'C$25M\' or null",\n'
        '  "dilution_shares_issued": "e.g. \'5M shares at C$5.00\' or null",\n'
        '  "permits_received": "e.g. \'Mine construction permit\' or null",\n'
        '  "management_changes": "e.g. \'New CEO appointed\' or null",\n'
        '  "ma_activity": "e.g. \'Acquired XYZ property for C$10M\' or null",\n'
        '  "resource_update": "e.g. \'+15% resource increase\' or null"\n'
        '}\n\nDocument text:\n'
    ),
    "presentation": (
        "You are a mining analyst. Extract the following fields from this corporate presentation. "
        "Return ONLY a valid JSON object — no markdown, no explanation. Use null for any field not found.\n\n"
        '{\n'
        '  "primary_commodity": "e.g. \'Gold\', \'Silver\', \'Copper\' or null",\n'
        '  "development_stage": "one of: Explorer, Developer, Producer, or null",\n'
        '  "upcoming_catalysts": "e.g. \'PFS expected Q3 2025\' or null",\n'
        '  "jurisdiction": "e.g. \'Sinaloa, Mexico\' or null",\n'
        '  "insider_ownership_pct": "e.g. \'18%\' or null",\n'
        '  "market_cap": "e.g. \'C$450M\' or null",\n'
        '  "enterprise_value": "e.g. \'C$630M\' or null"\n'
        '}\n\nDocument text (first 30,000 characters):\n'
    ),
    "proxy": (
        "You are a mining analyst. Extract the following fields from this Management Information Circular (Proxy). "
        "Return ONLY a valid JSON object — no markdown, no explanation. Use null for any field not found.\n\n"
        '{\n'
        '  "ceo_total_compensation": "e.g. \'C$2.1M\' or null",\n'
        '  "ceo_base_salary": "e.g. \'C$500K\' or null",\n'
        '  "ceo_shares_owned": "e.g. \'2.5M shares\' or null",\n'
        '  "board_size": "number of directors as integer or null",\n'
        '  "independent_directors_count": "number of independent directors as integer or null",\n'
        '  "related_party_transactions": "true if exist, false if none, null if unclear",\n'
        '  "say_on_pay_vote_pct": "e.g. \'92%\' or null",\n'
        '  "total_insider_ownership_pct": "e.g. \'22%\' or null"\n'
        '}\n\nDocument text (first 50,000 characters):\n'
    ),
}

# ── Core helpers ──────────────────────────────────────────────────────────────

def _extract_text(pdf_bytes: bytes) -> str:
    sample = pdf_bytes[:500].lstrip()
    if sample.startswith(b"<") or b"<!DOCTYPE" in sample[:100]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(pdf_bytes, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _call_gemini_json(prompt: str) -> dict | None:
    key = os.environ["GEMINI_API_KEY"]
    response = http.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
        timeout=60,
    )
    if not response.ok:
        print(f"  [Extractor] Gemini error: {response.status_code}")
        return None
    raw = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Strip markdown code fences if Gemini wrapped the JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [Extractor] JSON parse failed: {raw[:200]}")
        return None


def extract_facts(doc_type: str, text: str) -> dict | None:
    prompt_template = EXTRACTION_PROMPTS.get(doc_type)
    if not prompt_template:
        return None
    max_chars = 30_000 if doc_type == "presentation" else 50_000
    return _call_gemini_json(prompt_template + text[:max_chars])


def upsert_facts(company_name: str, doc_type: str, label: str, facts: dict) -> None:
    table = TABLE_FOR_TYPE[doc_type]
    sb = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    row = {"company_name": company_name, "document_label": label, "extracted_at": now, **facts}
    existing = sb.table(table).select("id").eq("company_name", company_name).eq("document_label", label).limit(1).execute()
    if existing.data:
        sb.table(table).update(row).eq("company_name", company_name).eq("document_label", label).execute()
    else:
        sb.table(table).insert(row).execute()


def generate_null_report(company_name: str) -> list[str]:
    sb = _get_supabase()
    nulls = []
    for table, fields in TABLE_FIELDS.items():
        rows = sb.table(table).select("*").eq("company_name", company_name).execute()
        if not rows.data:
            nulls.append(f"{table}: NO DATA — document not found or not classified")
            continue
        for row in rows.data:
            label = row.get("document_label", "unknown")
            for field in fields:
                if row.get(field) is None:
                    nulls.append(f"{table} [{label}]: {field} is NULL")
    return nulls


# ── Main entry point ──────────────────────────────────────────────────────────

def run_extraction(company_name: str, pdf_docs: dict[str, str]) -> list[str]:
    """
    Extract structured facts from all documents and store in Supabase.
    Accepts the UNFILTERED pdf_docs dict (label → url) so proxy documents
    are included. Returns a null report listing all missing fields.
    """
    from scraping import fetch_pdf_bytes

    for label, url in pdf_docs.items():
        doc_type = classify_document(label)
        if not doc_type:
            print(f"  [Extractor] Skipping unclassified: {label}")
            continue

        print(f"  [Extractor] {doc_type}: {label}")
        try:
            pdf_bytes = fetch_pdf_bytes(url)
            text = _extract_text(pdf_bytes)
        except Exception as e:
            print(f"  [Extractor] Read failed for {label}: {e}")
            continue

        facts = extract_facts(doc_type, text)
        if facts is None:
            print(f"  [Extractor] Extraction failed for {label}")
            continue

        try:
            upsert_facts(company_name, doc_type, label, facts)
            print(f"  [Extractor] Stored: {label}")
        except Exception as e:
            print(f"  [Extractor] Store failed for {label}: {e}")

    return generate_null_report(company_name)
