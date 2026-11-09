"""Shared image decoding for the quality gate and the inference engine.

Decoding happens once and the same ``DecodedImage`` is handed to both stages,
so the quality gate always judges exactly the pixels the model will see.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from src.inference.errors import InputMissingError, InputTooLargeError, InputUnreadableError, UnsupportedFormatError

DEFAULT_ALLOWED_FORMATS = ("PNG", "JPEG", "BMP", "TIFF", "WEBP")
DEFAULT_MAX_PIXELS = 50_000_000

ImageSource = bytes | str | Path


@dataclass(frozen=True)
class DecodedImage:
    image: Image.Image            # RGB, orientation already applied
    sha256: str                   # of the encoded input bytes
    source_format: str
    width: int
    height: int
    exif_orientation_applied: bool
    source_reference: str         # file path, or "<bytes>" for uploads

    def as_array(self) -> np.ndarray:
        return np.asarray(self.image, dtype=np.uint8)


def _read_bytes(source: ImageSource) -> tuple[bytes, str]:
    if isinstance(source, (bytes, bytearray)):
        if not source:
            raise InputMissingError("Image payload is empty")
        return bytes(source), "<bytes>"
    path = Path(source)
    if not path.is_file():
        raise InputMissingError(f"Image file not found: {path}", {"path": str(path)})
    data = path.read_bytes()
    if not data:
        raise InputMissingError(f"Image file is empty: {path}", {"path": str(path)})
    return data, str(path)


def decode_image(
    source: ImageSource,
    allowed_formats: Sequence[str] = DEFAULT_ALLOWED_FORMATS,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    apply_exif_orientation: bool = True,
) -> DecodedImage:
    """Decode an image into RGB, raising a typed ``InputError`` on any problem."""

    data, reference = _read_bytes(source)
    digest = hashlib.sha256(data).hexdigest()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as handle:
                source_format = (handle.format or "").upper()
                if source_format not in {fmt.upper() for fmt in allowed_formats}:
                    raise UnsupportedFormatError(
                        f"Format {source_format or 'unknown'} is not allowed",
                        {"format": source_format, "allowed": list(allowed_formats)},
                    )
                if handle.width * handle.height > max_pixels:
                    raise InputTooLargeError(
                        f"Image has {handle.width * handle.height} pixels (limit {max_pixels})",
                        {"width": handle.width, "height": handle.height, "max_pixels": max_pixels},
                    )
                handle.load()
                orientation = handle.getexif().get(0x0112, 1)  # EXIF Orientation tag
                rotated = apply_exif_orientation and orientation not in (None, 1)
                oriented = ImageOps.exif_transpose(handle) if rotated else handle
                image = oriented.convert("RGB")
    except (UnsupportedFormatError, InputTooLargeError):
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InputTooLargeError(f"Image rejected as a decompression bomb: {error}") from error
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise InputUnreadableError(f"Image could not be decoded: {error}", {"source": reference}) from error
    if image.width == 0 or image.height == 0:
        raise InputUnreadableError("Image has a zero dimension", {"source": reference})
    return DecodedImage(image, digest, source_format, image.width, image.height, bool(rotated), reference)
