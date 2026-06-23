"""
ingestion/text_extraction.py

Shared text extraction for any uploaded file (field report submissions,
ad-hoc chat attachments) — PDF/DOCX/TXT/MD, with OCR fallback for scans
and images. Originally lived only in reports/reviewer.py; pulled out here
so the chat upload endpoint can reuse the exact same logic.
"""

import os
from typing import Optional

from app.ingestion.document_loader import _load_pdf, _load_docx, _load_txt


def extract_text(file_path: str) -> tuple[str, bool, Optional[float]]:
    """
    Returns (extracted_text, ocr_used, ocr_confidence).

    ocr_confidence is Tesseract's average per-word confidence (0-100) when
    OCR ran, or None for files that didn't need OCR. Callers that care about
    extraction reliability (e.g. the reviewer deciding whether to trust a
    scan enough to auto-reject it) should check this — low confidence often
    means checkboxes/handwriting/cursive fonts didn't survive extraction,
    not that the source document is actually deficient.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in {".png", ".jpg", ".jpeg"}:
        from app.ingestion.ocr_service import extract_text_from_image
        text, confidence = extract_text_from_image(file_path)
        return text, True, confidence

    if ext == ".pdf":
        from app.ingestion.ocr_service import is_scanned_pdf, extract_text_from_scanned_pdf
        if is_scanned_pdf(file_path):
            text, confidence = extract_text_from_scanned_pdf(file_path)
            return text, True, confidence
        docs = _load_pdf(file_path)
        return "\n\n".join(d.page_content for d in docs), False, None

    loader_map = {".docx": _load_docx, ".txt": _load_txt, ".md": _load_txt}
    loader = loader_map.get(ext)
    if not loader:
        return "", False, None
    docs = loader(file_path)
    return "\n\n".join(d.page_content for d in docs), False, None
