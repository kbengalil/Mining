import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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


def find_pdf_links(company_name: str) -> dict:
    company = COMPANIES[company_name]
    base_url = company["base_url"]
    pdf_links = {}
    page_errors = []

    for page_path in company["investor_pages"]:
        url = base_url + page_path
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.Timeout:
            page_errors.append({"page": url, "reason": "Timed out — site took too long to respond"})
            continue
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 403:
                reason = "Blocked by the site (403 Forbidden) — it may be detecting automated requests"
            elif status == 404:
                reason = "Page not found (404) — the URL may have changed"
            else:
                reason = f"Site returned an error (HTTP {status})"
            page_errors.append({"page": url, "reason": reason})
            continue
        except requests.RequestException as e:
            page_errors.append({"page": url, "reason": f"Could not connect: {e}"})
            continue

        soup = BeautifulSoup(response.text, "html.parser")
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


def scrape_about_pages(company_name: str) -> str:
    company = COMPANIES[company_name]
    base_url = company["base_url"]
    texts = []
    for path in company.get("about_pages", []):
        url = base_url + path
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            texts.append(f"--- {url} ---\n{text}")
        except Exception as e:
            print(f"  Could not scrape {url}: {e}")
    return "\n\n".join(texts)


def scrape_news(company_name: str, min_items: int = 5, max_items: int = 10) -> list[dict]:
    company = COMPANIES[company_name]
    news_path = company.get("news_page")
    if not news_path:
        return []

    news_url = company["base_url"] + news_path
    try:
        r = requests.get(news_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"  Could not scrape news from {news_url}: {e}")
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
