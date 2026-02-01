"""OCR handlers for extracting text from images."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class OCRMethod(str, Enum):
    """Available OCR methods."""

    PYTESSERACT = "pytesseract"
    TROCR = "trocr"
    VISION = "vision"


@dataclass
class OCRResult:
    """Result of OCR processing."""

    text: str
    confidence: float | None = None
    method: str = "pytesseract"


class OCRError(Exception):
    """Error during OCR processing."""

    pass


def ocr_with_pytesseract(image_path: Path) -> OCRResult:
    """
    Extract text from image using pytesseract.

    Args:
        image_path: Path to the image file

    Returns:
        OCRResult with extracted text

    Raises:
        OCRError: If pytesseract is not installed or processing fails
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise OCRError(
            f"pytesseract or Pillow not installed. Install with: pip install pytesseract Pillow\n{e}"
        )

    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return OCRResult(text=text.strip(), method="pytesseract")
    except Exception as e:
        raise OCRError(f"pytesseract OCR failed for {image_path}: {e}")


def ocr_with_trocr(image_path: Path, cache_dir: Path | None = None) -> OCRResult:
    """
    Extract text from image using TrOCR (handwriting-optimized).

    Args:
        image_path: Path to the image file
        cache_dir: Directory to cache the model

    Returns:
        OCRResult with extracted text

    Raises:
        OCRError: If transformers is not installed or processing fails
    """
    try:
        from PIL import Image
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except ImportError as e:
        raise OCRError(
            f"transformers or Pillow not installed. Install with: pip install transformers Pillow\n{e}"
        )

    try:
        model_name = "microsoft/trocr-base-handwritten"

        # Load model and processor
        processor = TrOCRProcessor.from_pretrained(
            model_name, cache_dir=cache_dir
        )
        model = VisionEncoderDecoderModel.from_pretrained(
            model_name, cache_dir=cache_dir
        )

        # Process image
        image = Image.open(image_path).convert("RGB")
        pixel_values = processor(images=image, return_tensors="pt").pixel_values

        # Generate text
        generated_ids = model.generate(pixel_values)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        return OCRResult(text=text.strip(), method="trocr")
    except Exception as e:
        raise OCRError(f"TrOCR processing failed for {image_path}: {e}")


def ocr_with_vision_llm(image_path: Path, settings: object | None = None) -> OCRResult:
    """
    Extract text from image using a vision-capable LLM.

    Args:
        image_path: Path to the image file
        settings: Settings object with LLM configuration

    Returns:
        OCRResult with extracted text

    Raises:
        OCRError: If LLM integration is not configured or processing fails
    """
    # Vision LLM support is a future enhancement
    raise OCRError(
        "Vision LLM OCR is not yet implemented. "
        "Use --ocr=pytesseract or --ocr=trocr instead."
    )


def perform_ocr(
    image_path: Path,
    method: OCRMethod | str = OCRMethod.PYTESSERACT,
    cache_dir: Path | None = None,
    settings: object | None = None,
) -> OCRResult:
    """
    Extract text from an image using the specified OCR method.

    Args:
        image_path: Path to the image file
        method: OCR method to use ('pytesseract', 'trocr', or 'vision')
        cache_dir: Directory to cache models (for trocr)
        settings: Settings object (for vision LLM)

    Returns:
        OCRResult with extracted text

    Raises:
        OCRError: If OCR processing fails
    """
    if isinstance(method, str):
        method = OCRMethod(method)

    if method == OCRMethod.PYTESSERACT:
        return ocr_with_pytesseract(image_path)
    elif method == OCRMethod.TROCR:
        return ocr_with_trocr(image_path, cache_dir=cache_dir)
    elif method == OCRMethod.VISION:
        return ocr_with_vision_llm(image_path, settings=settings)
    else:
        raise OCRError(f"Unknown OCR method: {method}")
