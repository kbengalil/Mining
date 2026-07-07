import json
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

COMPANIES = {
    "First Mining Gold": {
        "base_url": "https://www.firstmininggold.com",
        "investor_pages": [
            "/investors/investor-downloads/",
            "/investors/reports-filings/financials/",
            "/investors/reports-filings/annual-information-form/",
            "/investors/agm/",
        ],
        "about_pages": [
            "/about/management/",
        ],
        "news_page": "/news/",
    }
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def identify_company_from_url(url: str) -> str | None:
    """Ask Gemini to identify a mining company from its website URL."""
    key = os.environ["GEMINI_API_KEY"]
    prompt = f'What is the official name of the publicly traded mining company at {url}? Return ONLY the company name, nothing else.'
    resp = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
        timeout=30,
    )
    if not resp.ok:
        return None
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def discover_company(company_name: str, base_url: str | None = None) -> dict | None:
    """Find a mining company's investor page paths.

    If base_url is provided, skips Google Search and asks Gemini to find
    the sub-page paths on the known domain. Otherwise uses Google Search
    grounding to find the domain first.
    """
    key = os.environ["GEMINI_API_KEY"]

    if base_url:
        # User provided the URL — just find the sub-pages on that domain
        base_url = base_url.rstrip("/")
        prompt = f"""The mining company "{company_name}" has its website at {base_url}.

Find the correct paths on this website for:
- investor_pages: pages that contain PDF documents (Annual Information Form, Management Information Circular, corporate presentations, financial statements)
- about_pages: management team or leadership page
- news_page: press releases or news page

Return ONLY a JSON object:
{{
  "base_url": "{base_url}",
  "investor_pages": ["/investors/", "/investors/reports/"],
  "about_pages": ["/about/team/"],
  "news_page": "/news/"
}}

Rules:
- All paths must start with /
- Return ONLY valid JSON, no explanation"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
    else:
        prompt = f"""Find the official investor relations website for the publicly traded mining company "{company_name}".

Return ONLY a JSON object with these fields:
{{
  "base_url": "https://www.example.com",
  "investor_pages": ["/investors/", "/investors/reports/"],
  "about_pages": ["/about/team/"],
  "news_page": "/news/"
}}

Rules:
- base_url must be the company's official domain (no trailing slash)
- investor_pages: pages that contain links to PDF documents like Annual Information Form, Management Information Circular, corporate presentations, financial statements
- about_pages: management team or leadership page
- news_page: press releases or news page
- All paths must start with /
- Return ONLY valid JSON, no explanation"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
        }

    resp = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        print(f"discover_company failed: {resp.status_code} {resp.text[:200]}")
        return None
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except Exception as e:
        print(f"discover_company JSON parse error: {e}")
        return None


def _get_page_html(url: str) -> str:
    """Fetch fully-rendered HTML using Playwright (handles JS-rendered sites)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            ignore_https_errors=True,
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Scroll to trigger lazy loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            # Click any "Load More" / "Show More" buttons
            for selector in [
                "button:has-text('Load More')",
                "button:has-text('Show More')",
                "a:has-text('Load More')",
                "button:has-text('View All')",
            ]:
                try:
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1500)
                except Exception:
                    pass
            return page.content()
        finally:
            ctx.close()
            browser.close()


def find_pdf_links(company_name: str, dynamic_companies: dict | None = None) -> dict:
    all_companies = {**COMPANIES, **(dynamic_companies or {})}
    company = all_companies[company_name]
    base_url = company["base_url"]
    pdf_links = {}
    page_errors = []

    for page_path in company["investor_pages"]:
        url = base_url + page_path
        try:
            html = _get_page_html(url)
        except Exception as e:
            # Playwright failed — fall back to simple requests
            try:
                response = requests.get(url, headers=HEADERS, timeout=20, verify=False)
                response.raise_for_status()
                html = response.text
            except requests.HTTPError as he:
                status = he.response.status_code if he.response is not None else None
                if status == 403:
                    reason = "Blocked by the site (403 Forbidden)"
                elif status == 404:
                    reason = "Page not found (404)"
                else:
                    reason = f"HTTP {status}"
                page_errors.append({"page": url, "reason": reason})
                continue
            except Exception as re:
                page_errors.append({"page": url, "reason": str(re)})
                continue

        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(url, anchor["href"])
            if ".pdf" in href.lower():
                label = anchor.get_text(strip=True) or href.split("/")[-1].split("?")[0]
                pdf_links[label] = href

    return {"documents": pdf_links, "errors": page_errors}


INVALID_FILENAME_CHARS = '\\/:*?"<>|\n\r\t'


def sanitize_filename(label: str) -> str:
    cleaned = "".join("_" if c in INVALID_FILENAME_CHARS else c for c in label)
    cleaned = "_".join(cleaned.split())
    return cleaned.strip("_") or "document"


def scrape_about_pages(company_name: str, dynamic_companies: dict | None = None) -> str:
    all_companies = {**COMPANIES, **(dynamic_companies or {})}
    company = all_companies[company_name]
    base_url = company["base_url"]
    texts = []
    for path in company.get("about_pages", []):
        url = base_url + path
        try:
            html = _get_page_html(url)
        except Exception:
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                r.raise_for_status()
                html = r.text
            except Exception as e:
                print(f"  Could not scrape {url}: {e}")
                continue
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        texts.append(f"--- {url} ---\n{text}")
    return "\n\n".join(texts)


def scrape_news(company_name: str, min_items: int = 5, max_items: int = 10, dynamic_companies: dict | None = None) -> list[dict]:
    all_companies = {**COMPANIES, **(dynamic_companies or {})}
    company = all_companies[company_name]
    news_path = company.get("news_page")
    if not news_path:
        return []

    news_url = company["base_url"] + news_path
    try:
        html = _get_page_html(news_url)
    except Exception:
        try:
            r = requests.get(news_url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            html = r.text
        except Exception as e:
            print(f"  Could not scrape news from {news_url}: {e}")
            return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"  Could not parse news from {news_url}: {e}")
        return []

    # Parse "Mon DD, YYYY Headline text" pairs from page text
    date_re = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s{1,3}(\d{1,2}),\s+(\d{4})")
    matches = list(date_re.finditer(text))

    items = []
    for i, m in enumerate(matches):
        date_str = m.group(0)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else start + 300
        headline = " ".join(text[start:end].split()).strip()[:250]
        if len(headline) < 10:
            continue
        try:
            date = datetime.strptime(date_str.replace("  ", " "), "%b %d, %Y")
            items.append({"date": date, "date_str": date_str, "headline": headline})
        except ValueError:
            continue

    # Newest first, deduplicate by headline
    items.sort(key=lambda x: x["date"], reverse=True)
    seen = set()
    unique = []
    for item in items:
        if item["headline"] not in seen:
            seen.add(item["headline"])
            unique.append(item)

    # 6-month window with min_items fallback, capped at max_items
    cutoff = datetime.now() - timedelta(days=180)
    recent = [i for i in unique if i["date"] >= cutoff]
    result = recent if len(recent) >= min_items else unique
    return result[:max_items]


def fetch_pdf_bytes(url: str) -> bytes:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.content
