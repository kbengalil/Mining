import streamlit as st
import requests
import pdfplumber
import io
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

SAVE_LOCATIONS = {
    "Desktop": Path.home() / "OneDrive" / "Desktop",
    "Documents": Path.home() / "Documents",
    "This project folder": Path(__file__).parent / "data",
}

COMPANIES = {
    "First Mining Gold": {
        "base_url": "https://www.firstmininggold.com",
        "investor_pages": [
            "/investors/investor-downloads/",
            "/investors/reports-filings/financials/",
            "/investors/reports-filings/annual-information-form/",
        ],
    }
}

def find_pdf_links(company_name):
    company = COMPANIES[company_name]
    base_url = company["base_url"]
    pdf_links = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for page_path in company["investor_pages"]:
            url = base_url + page_path
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                anchors = page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(el => ({href: el.href, text: el.innerText.trim()}))"
                )
                for anchor in anchors:
                    href = anchor["href"]
                    if ".pdf" in href.lower():
                        label = anchor["text"] or href.split("/")[-1].split("?")[0]
                        pdf_links[label] = href
            except Exception as e:
                st.warning(f"Could not load {url}: {e}")

        browser.close()

    return pdf_links


def get_company_pdf_folder(location_name, company_name):
    base = SAVE_LOCATIONS[location_name]
    company_folder = base / company_name.replace(" ", "_")
    pdf_folder = company_folder / "Company's PDFs"
    pdf_folder.mkdir(parents=True, exist_ok=True)
    return pdf_folder


def fetch_pdf_bytes(pdf_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        response = context.request.get(pdf_url)
        pdf_bytes = response.body()
        browser.close()
    return pdf_bytes


INVALID_FILENAME_CHARS = '\\/:*?"<>|\n\r\t'

def sanitize_filename(label):
    cleaned = "".join("_" if c in INVALID_FILENAME_CHARS else c for c in label)
    cleaned = "_".join(cleaned.split())
    return cleaned.strip("_")


def save_pdf(label, url, folder):
    pdf_bytes = fetch_pdf_bytes(url)
    file_name = sanitize_filename(label) + ".pdf"
    file_path = folder / file_name
    file_path.write_bytes(pdf_bytes)
    return file_path


st.set_page_config(page_title="Mining AI Analyst", layout="wide")
st.title("Mining AI Analyst")

company_name = st.selectbox("Select company", list(COMPANIES.keys()))
location_name = st.selectbox("Save location", list(SAVE_LOCATIONS.keys()))

pdf_folder = get_company_pdf_folder(location_name, company_name)
st.caption(f"Files will be saved to: {pdf_folder}")

if st.button("Load available documents"):
    with st.spinner("Scanning investor pages for PDFs..."):
        pdf_links = find_pdf_links(company_name)
        st.session_state.pdf_links = pdf_links

if "pdf_links" in st.session_state and st.session_state.pdf_links:
    pdf_links = st.session_state.pdf_links
    mode = st.radio("Documents to download", ["Download all", "Select specific documents"])

    labels_to_fetch = list(pdf_links.keys())
    if mode == "Select specific documents":
        labels_to_fetch = [
            label for label in pdf_links
            if st.checkbox(label, value=False)
        ]

    if st.button("Fetch PDF(s)"):
        if not labels_to_fetch:
            st.warning("No documents selected.")
        else:
            with st.spinner(f"Downloading {len(labels_to_fetch)} PDF(s)..."):
                for label in labels_to_fetch:
                    try:
                        file_path = save_pdf(label, pdf_links[label], pdf_folder)
                        st.success(f"Saved: {file_path}")
                    except Exception as e:
                        st.error(f"Failed to fetch '{label}': {e}")

elif "pdf_links" in st.session_state and not st.session_state.pdf_links:
    st.warning("No PDFs found on the investor pages.")
