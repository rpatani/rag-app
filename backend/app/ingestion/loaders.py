from pathlib import Path

from docx import Document as DocxDocument
from pdf2image import convert_from_path
from PIL import Image
from pypdf import PdfReader

from app.core.ocr.factory import get_ocr_extractor

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

# Minimum characters from pypdf before assuming the PDF is a scanned image
_OCR_FALLBACK_THRESHOLD = 100

# 400 DPI for reliable OCR on printed text; 300 was too low for noisy scans
_OCR_DPI = 400


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return _ocr_image(path)

    raise ValueError(f"Unsupported file type: {suffix}")


def _load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages_text)

    if len(text.strip()) >= _OCR_FALLBACK_THRESHOLD:
        return "\n\n".join(
            f"[Page {i + 1}]\n{t}" for i, t in enumerate(pages_text) if t.strip()
        )

    # Scanned PDF — convert at high DPI then OCR each page
    ocr = get_ocr_extractor()
    images = convert_from_path(str(path), dpi=_OCR_DPI)
    ocr_pages = [ocr.extract_text(img) for img in images]
    return "\n\n".join(
        f"[Page {i + 1}]\n{t}" for i, t in enumerate(ocr_pages) if t.strip()
    )


def _load_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _ocr_image(path: Path) -> str:
    return get_ocr_extractor().extract_text(Image.open(path))
