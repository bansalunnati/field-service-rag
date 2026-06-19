FROM python:3.11.9-slim

# Install system dependencies (tesseract for OCR, poppler for scanned PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/uploaded_files data/submitted_reports

CMD uvicorn main:app --host 0.0.0.0 --port $PORT
