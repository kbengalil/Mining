"""
Compare two Mining AI Analyst reports.

Usage:
  python compare_reports.py "First Mining Gold"
      — compares current report vs archived (_First Mining Gold) from Supabase

  python compare_reports.py "First Mining Gold" --old-file old.md --new-file new.md
      — compares two local markdown files
"""

import argparse
import os
import re
import sys
from pathlib import Path

import requests as http
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SECTIONS = [
    "Company Snapshot",
    "The Team",
    "Financials",
    "Key Project Metrics",
    "Jurisdiction",
    "Recent Developments",
    "Valuation vs Peers",
    "Strategic Outlook",
    "Red Flags",
]


def fetch_report(company_name: str) -> tuple[str, str]:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    row = sb.table("company_overviews").select("overview_markdown, generated_at").eq("company_name", company_name).limit(1).execute()
    if not row.data:
        raise ValueError(f"No report found for '{company_name}'")
    d = row.data[0]
    return d["overview_markdown"], (d.get("generated_at") or "")[:10]


def compare_with_gemini(old_md: str, new_md: str, old_label: str, new_label: str) -> str:
    prompt = f"""You are comparing two versions of a Mining AI Analyst report.

OLD REPORT ({old_label}):
{old_md}

---

NEW REPORT ({new_label}):
{new_md}

---

Produce a comparison in EXACTLY TWO parts:

PART 1 — KEY FIGURES
Compare every numeric figure (cash, net debt, shares, warrants, options, NPV, IRR, capex, mine life, production, CEO comp, cash burn, etc.).
Format as a markdown table with columns: Metric | {old_label} | {new_label} | Match
Use ✓ for same, ≠ for different. Include ALL figures, not just the ones that differ.

PART 2 — TEXT DIFFERENCES BY SECTION
For each section: Company Snapshot, The Team, Financials, Key Project Metrics, Jurisdiction, Recent Developments, Valuation vs Peers, Strategic Outlook, Red Flags:
- If essentially the same: write one line "[Section]: Same"
- If meaningfully different: list changes as + (added) or - (removed) bullets, max 5 per section

Be concise. Ignore minor wording changes — only flag meaningful content differences."""

    key = os.environ["GEMINI_API_KEY"]
    resp = http.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def main():
    parser = argparse.ArgumentParser(description="Compare two Mining AI Analyst reports")
    parser.add_argument("company", help="Company name (fetches current vs archived from Supabase)")
    parser.add_argument("--old-file", help="Path to old report .md file (skips Supabase fetch)")
    parser.add_argument("--new-file", help="Path to new report .md file (skips Supabase fetch)")
    args = parser.parse_args()

    if args.old_file and args.new_file:
        old_md = Path(args.old_file).read_text(encoding="utf-8")
        new_md = Path(args.new_file).read_text(encoding="utf-8")
        old_label = "OLD"
        new_label = "NEW"
    else:
        print(f"Fetching current report for '{args.company}'...")
        new_md, new_date = fetch_report(args.company)
        new_label = f"NEW ({new_date})"

        # Find most recent archived version (name starts with _<company>)
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
        archived_rows = sb.table("company_overviews").select("company_name, overview_markdown, generated_at") \
            .ilike("company_name", f"_{args.company}%").order("generated_at", desc=True).limit(1).execute()
        if not archived_rows.data:
            print(f"No archived report found for '{args.company}'")
            sys.exit(1)
        d = archived_rows.data[0]
        old_md = d["overview_markdown"]
        old_date = (d.get("generated_at") or "")[:10]
        archived_name = d["company_name"]
        print(f"Found archived report: '{archived_name}'")
        old_label = f"OLD ({old_date})"

    print(f"\nComparing reports: {old_label} vs {new_label}\n")
    print("Running comparison with Gemini...\n")

    result = compare_with_gemini(old_md, new_md, old_label, new_label)

    print("=" * 80)
    print(f"REPORT COMPARISON: {args.company}")
    print("=" * 80)
    print(result)


if __name__ == "__main__":
    main()
