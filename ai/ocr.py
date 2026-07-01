from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from PIL import Image


@dataclass
class ExtractionResult:
    engine: str
    raw_text: str
    fields: dict
    confidence: float
    error: str | None = None


def extract_with_tesseract(image_bytes: bytes) -> ExtractionResult:
    try:
        import pytesseract
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        raw_text = pytesseract.image_to_string(image)
        if not raw_text.strip():
            return ExtractionResult("Local OCR", "", {}, 0.0, "No text detected by Tesseract.")
        return ExtractionResult("Local OCR", raw_text, {}, 0.70)
    except Exception as exc:
        return ExtractionResult("Local OCR", "", {}, 0.0, str(exc))
