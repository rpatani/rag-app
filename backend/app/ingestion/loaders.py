from pathlib import Path

import pytesseract
from docx import Document as DocxDocument
from pdf2image import convert_from_path
from PIL import Image
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

# Minimum characters from pypdf before assuming the PDF is a scanned image
_OCR_FALLBACK_THRESHOLD = 100


def load_text(path: Path) -> str:
    """Extract raw text from a supported document file."""
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
        return text

    # Scanned PDF — convert pages to images and OCR each one
    images = convert_from_path(str(path))
    return "\n\n".join(pytesseract.image_to_string(img) for img in images)


def _load_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _ocr_image(path: Path) -> str:
    return pytesseract.image_to_string(Image.open(path))
