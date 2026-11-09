"""REQ-P10-S03-002: no EXIF, GPS or text metadata survives into storage, and pixels never change."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import text

from src.preprocessing.decode import decode_image
from src.preprocessing.sanitise import sanitise_image
from tests.worker.conftest import verified_upload

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def _pixels(seed: int = 3, size=(256, 200)) -> Image.Image:
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))


def _jpeg(orientation: int | None = None, gps: bool = True) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "Synthetic Camera"
    if orientation:
        exif[ORIENTATION] = orientation
    if gps:
        exif.get_ifd(GPS_IFD).update({1: "N", 2: (51.0, 30.0, 12.5), 3: "W", 4: (0.0, 7.0, 39.0)})
    buffer = io.BytesIO()
    _pixels().save(buffer, format="JPEG", quality=92, exif=exif, comment=b"patient name here")
    return buffer.getvalue()


def _png_with_text() -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Dr Example")
    info.add_itxt("Location", "Ward 7", zip=True)
    exif = Image.Exif()
    exif.get_ifd(GPS_IFD).update({1: "N", 2: (51.0, 30.0, 12.5)})
    buffer = io.BytesIO()
    _pixels().save(buffer, format="PNG", pnginfo=info, exif=exif)
    return buffer.getvalue()


def _no_metadata(data: bytes) -> None:
    with Image.open(io.BytesIO(data)) as image:
        assert not image.getexif(), "EXIF survived"
        assert not getattr(image, "text", {}), "PNG text survived"
        assert "comment" not in image.info
    for marker in (b"Exif", b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"Synthetic Camera", b"patient name"):
        assert marker not in data


def test_gps_jpeg_loses_its_exif_and_keeps_every_pixel():
    data = _jpeg()
    assert b"Exif" in data
    clean, kind = sanitise_image(data)
    assert kind == "JPEG"
    _no_metadata(clean)
    assert np.array_equal(decode_image(clean).as_array(), decode_image(data).as_array())


def test_rotated_jpeg_becomes_a_png_of_what_the_model_sees():
    data = _jpeg(orientation=6)
    clean, kind = sanitise_image(data)
    assert kind == "PNG" and clean.startswith(b"\x89PNG")
    _no_metadata(clean)
    seen = decode_image(data).as_array()
    assert seen.shape[:2] == (256, 200)  # rotated a quarter turn
    assert np.array_equal(decode_image(clean).as_array(), seen)


def test_png_text_and_exif_chunks_are_dropped():
    data = _png_with_text()
    clean, kind = sanitise_image(data)
    assert kind == "PNG"
    _no_metadata(clean)
    assert np.array_equal(decode_image(clean).as_array(), decode_image(data).as_array())


def test_a_clean_image_is_left_as_it_is(image):
    clean, kind = sanitise_image(image)
    assert kind == "PNG" and clean == image


@pytest.mark.parametrize("make", [_jpeg, _png_with_text])
def test_only_the_clean_copy_is_stored(client, state, make):
    data = make()
    upload_id = verified_upload(client, data)
    with state.db.engine.connect() as connection:
        key = connection.scalar(text("SELECT storage_key FROM uploads WHERE upload_id = :id"), {"id": upload_id})
    stored = state.blobs.read(key)
    _no_metadata(stored)
    assert np.array_equal(decode_image(stored).as_array(), decode_image(data).as_array())
