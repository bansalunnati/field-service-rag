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
import pytesseract
from PIL import Image

# On Windows (local dev), Tesseract isn't on PATH so we point to it directly.
# On Linux (Render), it's installed via apt and lives on PATH — no override needed.
import sys, os as _os
if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r"D:\Gen ai project\tesseract.exe"


def extract_text_from_image(file_path: str) -> tuple[str, float]:
    """
    Read text from a single image file (PNG, JPG, JPEG).

    Steps:
      1. Open the image with Pillow.
      2. Convert to grayscale — black-and-white images work better for OCR.
      3. Run pytesseract to get text AND confidence scores per word.
      4. Return the extracted text and the average confidence (0–100).
    """
    # Open image and convert to grayscale for better OCR accuracy
    img = Image.open(file_path).convert("L")

    # image_to_data returns a dict with per-word info including confidence scores
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Confidence values of -1 mean the entry is a layout element (not a real word)
    confidences = [c for c in data["conf"] if int(c) != -1]
    avg_confidence = statistics.mean(confidences) if confidences else 0.0

    # Get the plain extracted text
    text = pytesseract.image_to_string(img)

    return text.strip(), round(avg_confidence, 1)


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
        # Grayscale conversion improves OCR on most scanned documents
        gray = page_img.convert("L")

        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        page_confs = [c for c in data["conf"] if int(c) != -1]
        all_confidences.extend(page_confs)

        page_text = pytesseract.image_to_string(gray)
        all_text_parts.append(page_text.strip())

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
