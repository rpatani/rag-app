import logging
import math

import pytesseract
from PIL import Image, ImageFilter

from app.core.ocr.base import OCRExtractor

logger = logging.getLogger(__name__)

# PSM 3: fully automatic page segmentation without orientation detection.
# Better than PSM 1 for mixed-layout forms where OSD can misfire.
_TESS_CONFIG = "--oem 3 --psm 3"

# Images larger than this are scaled down before OCR.
# 20 MP comfortably covers A4/Letter at 300 DPI (~8 MP) with headroom.
# Prevents memory exhaustion from abnormally large scans.
_MAX_OCR_PIXELS = 20_000_000


class TesseractOCR(OCRExtractor):
    def extract_text(self, image: Image.Image) -> str:
        return pytesseract.image_to_string(self._preprocess(image), config=_TESS_CONFIG)

    def _preprocess(self, image: Image.Image) -> Image.Image:
        image = image.convert("L")

        pixels = image.width * image.height
        if pixels > _MAX_OCR_PIXELS:
            scale = math.sqrt(_MAX_OCR_PIXELS / pixels)
            new_size = (int(image.width * scale), int(image.height * scale))
            logger.warning(
                "Image too large (%d×%d = %dMP) — scaling down to %d×%d before OCR",
                image.width, image.height, pixels // 1_000_000,
                new_size[0], new_size[1],
            )
            image = image.resize(new_size, Image.LANCZOS)

        # Median filter reduces scan noise without amplifying it.
        image = image.filter(ImageFilter.MedianFilter(size=3))
        return image
