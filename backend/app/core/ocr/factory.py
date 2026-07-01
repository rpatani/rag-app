from functools import lru_cache

from app.config import get_settings
from app.core.ocr.base import OCRExtractor


@lru_cache
def get_ocr_extractor() -> OCRExtractor:
    """
    Return an OCRExtractor based on settings.ocr_backend.

    To add a new provider (AWS Textract, Google Vision, ...), implement
    OCRExtractor in core/ocr/<provider>_ocr.py, add a branch here, and
    set OCR_BACKEND in .env.
    """
    backend = get_settings().ocr_backend.lower()

    if backend == "tesseract":
        from app.core.ocr.tesseract_ocr import TesseractOCR
        return TesseractOCR()

    raise ValueError(f"Unsupported OCR backend: {backend!r}. Supported: tesseract")
