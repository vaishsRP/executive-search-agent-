import re

import streamlit as st
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def extract_text_from_pdf(uploaded_file):
    """pull text out of an uploaded pdf, empty string if it fails."""
    if uploaded_file is None:
        return ""
    try:
        reader = PdfReader(uploaded_file)
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return clean_text("\n".join(pages))
    except (PdfReadError, OSError, ValueError) as exc:
        st.warning(f"couldn't read pdf: {exc}. paste the cv text instead.")
        return ""
    except Exception as exc:
        st.warning(f"unexpected error reading pdf: {exc}")
        return ""


def clean_text(text):
    """strip html, collapse whitespace, normalise line breaks."""
    if not text:
        return ""
    no_html = re.sub(r"<[^>]+>", " ", text)
    normalised = no_html.replace("\r\n", "\n").replace("\r", "\n")
    normalised = re.sub(r"\n{3,}", "\n\n", normalised)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalised.split("\n")]
    return "\n".join(lines).strip()
