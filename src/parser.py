"""PDF and text parsing utilities for candidate CVs.

This module isolates all file-reading and text-normalisation concerns so the
rest of the application can treat CV content as a clean Python string,
regardless of whether it originated from an uploaded PDF or pasted text.
"""

from __future__ import annotations

import re
from typing import Any

import streamlit as st
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def extract_text_from_pdf(uploaded_file: Any) -> str:
    """Extract concatenated text from every page of an uploaded PDF.

    Parameters
    ----------
    uploaded_file:
        A Streamlit ``UploadedFile`` (file-like) object produced by
        ``st.file_uploader``. It must be readable as a PDF.

    Returns
    -------
    str
        Cleaned text from all pages concatenated with newlines. Returns an
        empty string if the file cannot be parsed; a Streamlit warning is
        emitted in that case so the operator can react in the UI.
    """
    if uploaded_file is None:
        return ""

    try:
        reader = PdfReader(uploaded_file)
        pages_text = []
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                # Individual page failures should not abort the whole CV.
                pages_text.append("")
        raw_text = "\n".join(pages_text)
        return clean_text(raw_text)
    except (PdfReadError, OSError, ValueError) as exc:
        st.warning(f"Could not read PDF: {exc}. Please paste the CV text instead.")
        return ""
    except Exception as exc:  # Last-resort safety net for unexpected reader errors.
        st.warning(f"Unexpected error while reading PDF: {exc}.")
        return ""


def clean_text(text: str) -> str:
    """Normalise whitespace, line breaks and strip stray HTML tags.

    Parameters
    ----------
    text:
        Raw text extracted from a PDF or pasted by the user.

    Returns
    -------
    str
        A trimmed string with collapsed whitespace and no HTML tags.
    """
    if not text:
        return ""

    # Remove HTML tags if any leaked in from a copy-paste from a webpage.
    no_html = re.sub(r"<[^>]+>", " ", text)
    # Normalise Windows / Mac line endings to a single \n.
    normalised = no_html.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of blank lines into at most one blank line.
    normalised = re.sub(r"\n{3,}", "\n\n", normalised)
    # Collapse internal whitespace runs (but preserve line breaks).
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalised.split("\n")]
    return "\n".join(lines).strip()
