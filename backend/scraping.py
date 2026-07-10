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
    },
    "Osisko Development Corp.": {
        "base_url": "https://osiskodev.com",
        "investor_pages": [
            "/investors/",
            "/investors/presentations/",
            "/investors/financials/",
            "/investors/reports/",
        ],
        "about_pages": [
            "/about/team/",
        ],
        "news_page": "/investors/news/",
    },
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


_INVESTOR_KEYWORDS = {"investor", "invest", "presentation", "financial", "report", "annual", "agm", "news", "media", "press", "document", "filing", "disclosure"}
_ABOUT_KEYWORDS = {"team", "management", "leadership", "about", "people", "executive", "board"}


def _crawl_for_pdfs(start_url: str) -> dict:
    """
    Crawl a company website starting from start_url.
    Visit the start page, find internal links that look like investor/about/news sub-pages,
    visit each one, and collect all PDF links found. Returns a config dict.
    """
    from urllib.parse import urlparse

    parsed = urlparse(start_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc

    def get_html(url):
        # Try simple requests first (fast); fall back to Playwright only if content looks JS-rendered
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            r.raise_for_status()
            html = r.text
            # If the page has almost no content it's likely JS-rendered — try Playwright
            if html.count("<a ") < 5:
                return _get_page_html(url)
            return html
        except Exception:
            try:
                return _get_page_html(url)
            except Exception:
                return ""

    def extract_internal_links(html, current_url):
        soup = BeautifulSoup(html, "html.parser")
        links = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(current_url, a["href"]).split("?")[0].split("#")[0].rstrip("/")
            text = a.get_text(strip=True).lower()
            if domain not in href:
                continue
            path = href.replace(base_url, "") or "/"
            if path and path != "/":
                links[path] = text
        return links

    def extract_pdfs(html, page_url):
        soup = BeautifulSoup(html, "html.parser")
        pdfs = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(page_url, a["href"])
            if ".pdf" in href.lower():
                label = a.get_text(strip=True) or href.split("/")[-1].split("?")[0]
                pdfs[label] = href
        return pdfs

    # Step 1: load the start page
    print(f"Crawling {start_url}...")
    start_html = get_html(start_url)
    all_links = extract_internal_links(start_html, start_url)

    def _is_section_page(path: str) -> bool:
        # Section index pages have short paths (≤3 segments), e.g. /investors/ or /investors/presentations/
        # Article pages have long slugs like /news/equinox-gold-reports-176836-ounces-...
        segments = [s for s in path.strip("/").split("/") if s]
        if len(segments) > 3:
            return False
        # Skip paths where the last segment looks like a long article slug (>40 chars)
        if segments and len(segments[-1]) > 40:
            return False
        return True

    # Step 2: categorize links
    investor_paths, about_paths, news_path = [], [], None
    for path, text in all_links.items():
        if not _is_section_page(path):
            continue
        combined = (path + " " + text).lower()
        if any(kw in combined for kw in _INVESTOR_KEYWORDS):
            investor_paths.append(path)
        if any(kw in combined for kw in _ABOUT_KEYWORDS):
            about_paths.append(path)
        if not news_path and any(kw in combined for kw in {"news", "press", "release", "media"}):
            news_path = path

    # Step 3: BFS crawl — visit investor section pages up to 2 levels deep
    # Queue starts with pages found on the homepage that look like investor sections
    visited = {start_url}
    queue = [p for p in dict.fromkeys(investor_paths) if ".pdf" not in p.lower()]
    all_investor_paths = []
    depth = {p: 0 for p in queue}

    while queue and len(all_investor_paths) < 20:
        path = queue.pop(0)
        url = base_url + path
        if url in visited:
            continue
        visited.add(url)
        print(f"  Visiting {url}...")
        html = get_html(url)
        if not html:
            continue
        all_investor_paths.append(path)

        # Only go one level deeper from depth-0 pages
        if depth.get(path, 0) < 1:
            sub_links = extract_internal_links(html, url)
            for sub_path, sub_text in sub_links.items():
                sub_url = base_url + sub_path
                if sub_url in visited or ".pdf" in sub_url.lower():
                    continue
                if not _is_section_page(sub_path):
                    continue
                combined = (sub_path + " " + sub_text).lower()
                if any(kw in combined for kw in _INVESTOR_KEYWORDS):
                    if sub_path not in depth:
                        depth[sub_path] = depth.get(path, 0) + 1
                        queue.append(sub_path)

    return {
        "base_url": base_url,
        "investor_pages": list(dict.fromkeys(all_investor_paths)) or investor_paths,
        "about_pages": list(dict.fromkeys(about_paths))[:3],
        "news_page": news_path or "/news/",
    }


def discover_company(company_name: str, base_url: str | None = None) -> dict | None:
    """Discover a company's investor pages by actually crawling the website."""
    if base_url:
        return _crawl_for_pdfs(base_url)

    # No URL provided — use Gemini with Google Search to find the domain first
    key = os.environ["GEMINI_API_KEY"]
    prompt = f'What is the official investor relations URL for the publicly traded mining company "{company_name}"? Return ONLY the URL, nothing else.'
    resp = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"role": "user", "parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]},
        timeout=60,
    )
    if not resp.ok:
        return None
    found_url = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    url_match = re.search(r"https?://[^\s]+", found_url)
    if not url_match:
        return None
    return _crawl_for_pdfs(url_match.group(0))


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
        if ".pdf" in page_path.lower():
            continue
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
