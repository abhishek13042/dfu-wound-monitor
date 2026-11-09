"""Write the printable reference-marker sheet (P09-S01) as an A4 PDF.

The PDF is drawn at 300 dpi, so printing at 100% ("Actual size") gives a 40 mm marker and a 50 mm check square.
Measure the square with a ruler before using a print; a printer that scales the page gives every photo a wrong scale.

    python scripts/measurement/make_marker_sheet.py [--out docs/measurement/marker_sheet_v1.pdf]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.measurement.marker import MarkerConfig  # noqa: E402

DPI = 300
A4_MM = (210.0, 297.0)


def mm(value: float) -> int:
    return int(round(value / 25.4 * DPI))


def build(config: MarkerConfig) -> Image.Image:
    page = Image.new("L", (mm(A4_MM[0]), mm(A4_MM[1])), 255)
    draw = ImageDraw.Draw(page)
    title = ImageFont.load_default(size=mm(5))
    body = ImageFont.load_default(size=mm(3.4))
    left = mm(25)

    draw.text((left, mm(22)), "Wound photo reference marker", font=title, fill=0)
    lines = [
        f"ArUco {config.dictionary}, id {config.marker_id}, {config.side_mm:g} mm square. Config {config.version}.",
        "Print at 100% (Actual size), not Fit to page.",
        "Check with a ruler that the outlined square measures exactly 50 mm on each side.",
        "Lay the sheet flat beside the wound, at the same height, facing the camera.",
        "Keep the whole marker in the photo with a white margin around it. Do not fold or cover it.",
        "A marker that is cut off, too small or at a steep angle is ignored, and the reason is shown.",
    ]
    for index, line in enumerate(lines):
        draw.text((left, mm(34) + index * mm(6.2)), line, font=body, fill=0)

    side = mm(config.side_mm)
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, config.dictionary))
    marker = Image.fromarray(cv2.aruco.generateImageMarker(dictionary, config.marker_id, side).astype(np.uint8))
    top = mm(85)
    page.paste(marker, (left + mm(10), top + mm(10)))
    draw.text((left + mm(10), top + mm(10) + side + mm(4)), f"Marker: {config.side_mm:g} mm", font=body, fill=0)

    square = mm(50)
    sx, sy = left + mm(95), top + mm(5)
    draw.rectangle((sx, sy, sx + square - 1, sy + square - 1), outline=0, width=mm(0.3))
    draw.text((sx, sy + square + mm(4)), "Check square: 50 mm", font=body, fill=0)

    footer = "Research prototype. Not a medical device. Sizes from a single photo are estimates."
    draw.text((left, mm(A4_MM[1] - 25)), footer, font=body, fill=0)
    return page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--out", default=str(ROOT / "docs" / "measurement" / "marker_sheet_v1.pdf"))
    args = parser.parse_args(argv)
    config = MarkerConfig.load(args.config) if args.config else MarkerConfig.load()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    build(config).save(out, "PDF", resolution=DPI)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
