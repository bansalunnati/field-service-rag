"""
ingestion/text_extraction.py

Shared text extraction for any uploaded file (field report submissions,
ad-hoc chat attachments) — PDF/DOCX/TXT/MD, with OCR fallback for scans
and images. Originally lived only in reports/reviewer.py; pulled out here
so the chat upload endpoint can reuse the exact same logic.
"""

import os

from app.ingestion.document_loader import _load_pdf, _load_docx, _load_txt


def extract_text(file_path: str) -> tuple[str, bool]:
    """Returns (extracted_text, ocr_used)."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in {".png", ".jpg", ".jpeg"}:
        from app.ingestion.ocr_service import extract_text_from_image
        text, _ = extract_text_from_image(file_path)
        return text, True

    if ext == ".pdf":
        from app.ingestion.ocr_service import is_scanned_pdf, extract_text_from_scanned_pdf
        if is_scanned_pdf(file_path):
            text, _ = extract_text_from_scanned_pdf(file_path)
            return text, True
        docs = _load_pdf(file_path)
        return "\n\n".join(d.page_content for d in docs), False

    loader_map = {".docx": _load_docx, ".txt": _load_txt, ".md": _load_txt}
    loader = loader_map.get(ext)
    if not loader:
        return "", False
    docs = loader(file_path)
    return "\n\n".join(d.page_content for d in docs), False
