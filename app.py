import streamlit as st
import requests
import pdfplumber
import io
from playwright.sync_api import sync_playwright

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
                page.goto(url, wait_until="networkidle", timeout=15000)
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


def fetch_pdf_bytes(pdf_url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        response = context.request.get(pdf_url)
        pdf_bytes = response.body()
        browser.close()
    return pdf_bytes


st.set_page_config(page_title="Mining AI Analyst", layout="wide")
st.title("Mining AI Analyst")

company_name = st.selectbox("Select company", list(COMPANIES.keys()))

if st.button("Load available documents"):
    with st.spinner("Scanning investor pages for PDFs..."):
        pdf_links = find_pdf_links(company_name)
        st.session_state.pdf_links = pdf_links

if "pdf_links" in st.session_state and st.session_state.pdf_links:
    selected_label = st.selectbox("Select document", list(st.session_state.pdf_links.keys()))
    selected_url = st.session_state.pdf_links[selected_label]
    st.caption(f"URL: {selected_url}")

    if st.button("Fetch PDF"):
        with st.spinner("Downloading PDF..."):
            try:
                pdf_bytes = fetch_pdf_bytes(selected_url)
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.pdf_name = selected_label.replace(" ", "_") + ".pdf"
                st.success("PDF ready to download.")
            except Exception as e:
                st.error(f"Failed to fetch PDF: {e}")

    if "pdf_bytes" in st.session_state:
        st.download_button(
            label="Save PDF to your computer",
            data=st.session_state.pdf_bytes,
            file_name=st.session_state.pdf_name,
            mime="application/pdf",
        )

elif "pdf_links" in st.session_state and not st.session_state.pdf_links:
    st.warning("No PDFs found on the investor pages.")
