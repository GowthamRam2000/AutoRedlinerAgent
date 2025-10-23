import os
from typing import List, Tuple

from pypdf import PdfReader
from docx import Document


def detect_type_from_key(key: str) -> str:
    ext = os.path.splitext(key.lower())[-1].lstrip(".")
    if ext in ("pdf", "docx"):
        return ext
    raise ValueError(f"Unsupported file type: {ext}")


def parse_pdf(path: str, max_pages: int = 20) -> Tuple[List[str], int]:
    reader = PdfReader(path)
    pages = []
    total_pages = len(reader.pages)
    limit = min(total_pages, max_pages)
    for i in range(limit):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            text = ""
        pages.append(text)
    return pages, total_pages


def parse_docx(path: str, max_pages: int = 20) -> Tuple[List[str], int]:
    doc = Document(path)
    texts = []
    for p in doc.paragraphs:
        txt = (p.text or "").strip()
        if txt:
            texts.append(txt)
    content = "\n".join(texts)
    words = content.split()
    chunk_size = 1200
    pages = []
    for i in range(0, len(words), chunk_size):
        pages.append(" ".join(words[i : i + chunk_size]))
        if len(pages) >= max_pages:
            break
    if not pages:
        pages = [content]
    return pages, len(pages)

