

from __future__ import annotations

import io
import logging
from typing import NamedTuple

import httpx
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


class OCRResult(NamedTuple):
    

    text: str
    confidence: float


async def extract_text_from_image(url: str) -> OCRResult | None:

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Failed to download image for OCR: %s", exc)
        return None

    try:
        img = Image.open(io.BytesIO(resp.content))
    except Exception as exc:
        logger.error("Failed to open image for OCR: %s", exc)
        return None

    try:
       
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(img).strip()

       
        confidences = [
            int(c) for c, t in zip(data["conf"], data["text"]) if int(c) > 0 and t.strip()
        ]
        mean_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

        return OCRResult(text=text, confidence=mean_confidence)
    except Exception as exc:
        logger.error("Tesseract OCR failed: %s", exc)
        return None
