import os
from typing import List, Optional
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader


def load_documents(
    data_path: str = "data/policies",
    pipeline: Optional[str] = None,
) -> List[Document]:
    """
    Drop-in replacement for your original load_documents().
    Same signature — now also loads DOCX, TXT, MD, CSV.
    Stamps each doc with source + pipeline metadata for citations.
    """
    documents = []
    files = os.listdir(data_path)
    print(f"\nFound {len(files)} files in '{data_path}'\n")

    for file in files:
        file_path = os.path.join(data_path, file)
        ext = os.path.splitext(file)[1].lower()
        detected_pipeline = pipeline or _detect_pipeline(file)

        print(f"Loading: {file}  →  pipeline: {detected_pipeline}")

        try:
            if ext == ".pdf":
                docs = _load_pdf(file_path)
            elif ext == ".docx":
                docs = _load_docx(file_path)
            elif ext in (".txt", ".md"):
                docs = _load_txt(file_path)
            elif ext == ".csv":
                docs = _load_csv(file_path)
            else:
                print(f"  Skipping unsupported type: {ext}")
                continue

            for doc in docs:
                doc.metadata.setdefault("source", file)
                doc.metadata["pipeline"] = detected_pipeline

            print(f"  Loaded {len(docs)} pages")
            documents.extend(docs)

        except Exception as e:
            print(f"  ERROR loading {file}: {e}")

    return documents


def _load_pdf(path: str) -> List[Document]:
    # Your original loader — unchanged
    loader = PyPDFLoader(path)
    return loader.load()


def _load_docx(path: str) -> List[Document]:
    try:
        from langchain_community.document_loaders import Docx2txtLoader
        return Docx2txtLoader(path).load()
    except ImportError:
        from docx import Document as DocxDoc
        doc = DocxDoc(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [Document(page_content=text, metadata={"source": os.path.basename(path)})]


def _load_txt(path: str) -> List[Document]:
    from langchain_community.document_loaders import TextLoader
    return TextLoader(path, encoding="utf-8").load()


def _load_csv(path: str) -> List[Document]:
    import csv
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            line = ", ".join(f"{k}: {v}" for k, v in row.items() if v)
            rows.append(line)
    docs = []
    for i in range(0, len(rows), 50):
        block = "\n".join(rows[i: i + 50])
        docs.append(Document(
            page_content=block,
            metadata={"source": os.path.basename(path), "page": i // 50 + 1},
        ))
    return docs


def _detect_pipeline(filename: str) -> str:
    name = filename.lower()
    if any(k in name for k in ["manual", "service", "spec", "part", "equipment", "maintenance"]):
        return "technical"
    if any(k in name for k in ["policy", "compliance", "regulation", "procedure", "sop"]):
        return "policy"
    return "general"
