"""
ocr_service.py — Extract text from images and scanned PDFs using OCR.

What is OCR?
  OCR (Optical Character Recognition) reads text from images.
  We use pytesseract, which is a Python wrapper around the Tesseract OCR engine.

System requirement:
  Tesseract must be installed separately (it's not a Python package).

  Windows:
    Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
    Install it, then add to PATH (or set pytesseract.pytesseract.tesseract_cmd below).
    Default install path: C:\\Program Files\\Tesseract-OCR\\tesseract.exe

  macOS:
    brew install tesseract

  Linux (Ubuntu/Debian):
    sudo apt install tesseract-ocr

  After installing, verify with: tesseract --version
"""

import statistics
import sys
import os
import pytesseract
from PIL import Image

# OCR_TIMEOUT_SECONDS bounds how long a single Tesseract call may run.
# Without this, a large/dense image on a slow CPU (e.g. Render's free tier)
# can run long enough that the platform kills the worker outright — which
# surfaces to the client as a bare 502 with no useful error message at all.
# Failing fast here turns that into a clear, actionable 422 instead.
OCR_TIMEOUT_SECONDS = int(os.getenv("OCR_TIMEOUT_SECONDS", "25"))

# Cap the longest image dimension before OCR — this is the single biggest
# lever on both runtime and memory for pytesseract/Tesseract, and accuracy
# past ~2000px rarely improves for scanned documents or photos.
MAX_OCR_DIMENSION = int(os.getenv("MAX_OCR_DIMENSION", "2000"))

# On Windows (local dev), Tesseract isn't on PATH so we point to it directly.
# On Linux (Render), it's installed via apt and lives on PATH — no override needed.
# Override the default path via TESSERACT_CMD if your local install lives
# somewhere else — hardcoding one developer's path here breaks OCR for
# everyone else who clones this repo.
if sys.platform == "win32":
    _default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _cmd = os.getenv("TESSERACT_CMD", _default_win_path)
    if os.path.exists(_cmd):
        pytesseract.pytesseract.tesseract_cmd = _cmd
    # If neither TESSERACT_CMD nor the default path exists, leave pytesseract
    # to resolve "tesseract" from PATH — it'll raise a clear TesseractNotFoundError
    # instead of silently pointing at a binary that was never there.


def _downscale(img: Image.Image) -> Image.Image:
    """Shrinks an image so its longest side is at most MAX_OCR_DIMENSION."""
    longest = max(img.size)
    if longest <= MAX_OCR_DIMENSION:
        return img
    scale = MAX_OCR_DIMENSION / longest
    new_size = (int(img.width * scale), int(img.height * scale))
    return img.resize(new_size, Image.LANCZOS)


def _ocr_image(img: Image.Image) -> tuple[str, list]:
    """
    Runs Tesseract ONCE on a preprocessed image via image_to_data, and
    reconstructs both plain text (grouped by line) and per-word confidences
    from that single result — avoids OCR'ing the same image twice (once for
    text, once for confidence), which used to double runtime for no benefit.

    Raises:
        pytesseract.TesseractError if OCR exceeds OCR_TIMEOUT_SECONDS.
    """
    data = pytesseract.image_to_data(
        img, output_type=pytesseract.Output.DICT, timeout=OCR_TIMEOUT_SECONDS
    )

    lines: dict = {}
    confidences = []
    for word, conf, block, par, line in zip(
        data["text"], data["conf"], data["block_num"], data["par_num"], data["line_num"]
    ):
        if int(conf) == -1:
            continue
        confidences.append(conf)
        if word.strip():
            lines.setdefault((block, par, line), []).append(word)

    text = "\n".join(" ".join(words) for words in lines.values())
    return text.strip(), confidences


def extract_text_from_image(file_path: str) -> tuple[str, float]:
    """
    Read text from a single image file (PNG, JPG, JPEG).

    Opens the image with Pillow, downscales if oversized, converts to
    grayscale, then OCRs it. Returns the extracted text and the average
    word confidence (0-100).
    """
    img = _downscale(Image.open(file_path).convert("L"))
    text, confidences = _ocr_image(img)
    avg_confidence = statistics.mean(confidences) if confidences else 0.0
    return text, round(avg_confidence, 1)


def extract_text_from_scanned_pdf(file_path: str) -> tuple[str, float]:
    """
    Extract text from a scanned PDF by converting each page to an image first.

    Steps:
      1. Use pdf2image to convert PDF pages → PIL images (requires poppler).
      2. Convert each page image to grayscale.
      3. Run OCR on each page.
      4. Combine all pages into one text block.
      5. Return combined text and overall average confidence.

    System requirement for pdf2image:
      Windows: download poppler from https://github.com/oschwartz10612/poppler-windows
               extract it, and add the bin/ folder to your PATH.
      macOS:   brew install poppler
      Linux:   sudo apt install poppler-utils
    """
    import pdf2image  # imported here so missing install only fails for PDFs

    # Convert all PDF pages to PIL Image objects
    pages = pdf2image.convert_from_path(file_path)

    all_text_parts = []
    all_confidences = []

    for page_img in pages:
        # Grayscale + downscale improves both OCR accuracy and runtime
        gray = _downscale(page_img.convert("L"))
        page_text, page_confs = _ocr_image(gray)
        all_confidences.extend(page_confs)
        all_text_parts.append(page_text)

    combined_text = "\n\n".join(all_text_parts)
    avg_confidence = round(statistics.mean(all_confidences), 1) if all_confidences else 0.0

    return combined_text, avg_confidence


def is_scanned_pdf(file_path: str) -> bool:
    """
    Guess whether a PDF is scanned (image-only, no text layer).

    How: try to extract text with pypdf. If the whole file has fewer than
    100 characters of real text, it's almost certainly a scanned PDF.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        total_text = ""
        for page in reader.pages:
            total_text += page.extract_text() or ""
        return len(total_text.strip()) < 100
    except Exception:
        # If we can't read the PDF at all, assume it might need OCR
        return True
