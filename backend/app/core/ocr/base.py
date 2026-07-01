from abc import ABC, abstractmethod

from PIL import Image


class OCRExtractor(ABC):
    """Extract text from a single image."""

    @abstractmethod
    def extract_text(self, image: Image.Image) -> str:
        raise NotImplementedError
