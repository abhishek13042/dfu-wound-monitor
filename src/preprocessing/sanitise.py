"""P10-S03: remove EXIF and other metadata before an image is stored.

The sanitised bytes are the only copy kept (REQ-P10-S03-002), so the stored hash
is taken after this step.  Pixels never change:

- A JPEG with no rotation keeps its entropy-coded data byte for byte; only the
  APPn and COM segments go (APP0/JFIF and APP14/Adobe stay, because they decide
  how the colours decode).  Re-encoding a JPEG would shift every result.
- A PNG with no rotation keeps its critical chunks and ``tRNS``; every other
  ancillary chunk (``eXIf``, ``tEXt``, ``iTXt``, ``zTXt``, ``tIME``, ...) goes.
- Anything else, or any image whose EXIF asks for a rotation, is re-encoded as a
  metadata-free PNG of the oriented pixels, which is exactly what the model sees.

Every result is decoded again and compared with the original's pixels; a
mismatch falls back to the PNG re-encode, which cannot drift.
"""

from __future__ import annotations

import io
import struct
import zlib

import numpy as np
from PIL import Image

from src.preprocessing.decode import decode_image

_KEEP_JPEG_APP = {0xE0, 0xEE}            # APP0 (JFIF) and APP14 (Adobe colour transform)
_KEEP_PNG_CHUNKS = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SanitiseError(ValueError):
    """The input could not be rewritten without metadata."""


def _strip_jpeg(data: bytes) -> bytes:
    if data[:2] != b"\xff\xd8":
        raise SanitiseError("not a JPEG")
    out, pos = bytearray(b"\xff\xd8"), 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise SanitiseError("bad JPEG marker")
        marker = data[pos + 1]
        if marker == 0xFF:                 # fill byte
            pos += 1
            continue
        if marker == 0xDA:                 # start of scan: the rest is image data
            out += data[pos:]
            return bytes(out)
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            out += data[pos:pos + 2]
            pos += 2
            continue
        (length,) = struct.unpack(">H", data[pos + 2:pos + 4])
        segment = data[pos:pos + 2 + length]
        if len(segment) != 2 + length:
            raise SanitiseError("truncated JPEG segment")
        if not ((0xE0 <= marker <= 0xEF and marker not in _KEEP_JPEG_APP) or marker == 0xFE):
            out += segment
        pos += 2 + length
    raise SanitiseError("JPEG has no image data")


def _strip_png(data: bytes) -> bytes:
    if not data.startswith(_PNG_SIGNATURE):
        raise SanitiseError("not a PNG")
    out, pos = bytearray(_PNG_SIGNATURE), len(_PNG_SIGNATURE)
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        chunk = data[pos:pos + 12 + length]
        if len(chunk) != 12 + length:
            raise SanitiseError("truncated PNG chunk")
        if kind in _KEEP_PNG_CHUNKS:
            out += chunk
        pos += 12 + length
        if kind == b"IEND":
            return bytes(out)
    raise SanitiseError("PNG has no IEND")


def _reencode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)  # Pillow writes no metadata unless asked
    return buffer.getvalue()


def sanitise_image(data: bytes) -> tuple[bytes, str]:
    """Return ``data`` without metadata, and its format; decoded pixels are identical."""

    original = decode_image(data)
    reference = original.as_array()
    candidate: bytes | None = None
    if not original.exif_orientation_applied:
        try:
            if original.source_format == "JPEG":
                candidate = _strip_jpeg(data)
            elif original.source_format == "PNG":
                candidate = _strip_png(data)
        except (SanitiseError, struct.error, IndexError, zlib.error):
            candidate = None
    if candidate is not None:
        try:
            if np.array_equal(decode_image(candidate).as_array(), reference):
                return candidate, original.source_format
        except Exception:  # noqa: BLE001 - any failure falls back to the re-encode below
            pass
    rewritten = _reencode_png(original.image)
    if not np.array_equal(decode_image(rewritten).as_array(), reference):  # pragma: no cover - RGB PNG is lossless
        raise SanitiseError("re-encoded image does not match the original pixels")
    return rewritten, "PNG"
