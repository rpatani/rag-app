import pytesseract
from PIL import Image, ImageFilter

from app.core.ocr.base import OCRExtractor

# PSM 3: fully automatic page segmentation without orientation detection.
# Better than PSM 1 for mixed-layout forms where OSD can misfire.
_TESS_CONFIG = "--oem 3 --psm 3"


class TesseractOCR(OCRExtractor):
    def extract_text(self, image: Image.Image) -> str:
        return pytesseract.image_to_string(self._preprocess(image), config=_TESS_CONFIG)

    def _preprocess(self, image: Image.Image) -> Image.Image:
        # Grayscale first, then median filter to reduce scan noise without
        # amplifying it (contrast boost + sharpen was making things worse).
        image = image.convert("L")
        image = image.filter(ImageFilter.MedianFilter(size=3))
        return image
