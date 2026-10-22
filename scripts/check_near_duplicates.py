"""Report perceptual near-duplicates within and across image collections.

Each ``--collection NAME=DIR`` is scanned recursively for images.  Pairs with
a 64-bit pHash Hamming distance <= ``--max-hamming`` are reported, split into
within-collection and cross-collection pairs.

    python scripts/check_near_duplicates.py \
        --collection "FUSeg2021=data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge" \
        --collection "LowerLimbV3=data/raw/LowerLimbFeetWound/V3/extracted/wound_main" \
        --collection "DFUTissue=data/raw/DFUTissueSegNet/source/DFUTissue" \
        --output reports/near_duplicate_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.data.near_duplicates import (  # noqa: E402
    DEFAULT_MAX_HAMMING_DISTANCE,
    compute_phash_for_path,
    find_near_duplicate_pairs,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
MASK_DIRECTORY_HINTS = {"labels", "label", "masks", "mask", "wound_mask", "annotations"}


def collect_images(root: Path) -> list[Path]:
    """Images under ``root``, skipping directories that hold masks."""

    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in IMAGE_SUFFIXES
        and not MASK_DIRECTORY_HINTS.intersection(part.lower() for part in path.relative_to(root).parts[:-1])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collection", action="append", required=True, help="NAME=DIRECTORY")
    parser.add_argument("--max-hamming", type=int, default=DEFAULT_MAX_HAMMING_DISTANCE)
    parser.add_argument("--output", default="reports/near_duplicate_report.json")
    args = parser.parse_args()

    hashes: dict[str, int] = {}
    counts: dict[str, int] = {}
    for item in args.collection:
        name, _, directory = item.partition("=")
        root = Path(directory) if Path(directory).is_absolute() else project_root / directory
        if not name or not root.is_dir():
            raise SystemExit(f"Invalid collection '{item}'")
        images = collect_images(root)
        counts[name] = len(images)
        for path in images:
            hashes[f"{name}::{path.relative_to(root).as_posix()}"] = compute_phash_for_path(path)
        print(f"{name}: hashed {len(images)} images")

    pairs = find_near_duplicate_pairs(hashes, args.max_hamming)
    cross = [pair for pair in pairs if pair[0].split("::")[0] != pair[1].split("::")[0]]
    within = [pair for pair in pairs if pair not in cross]
    report = {
        "method": "64-bit DCT pHash",
        "max_hamming_distance": args.max_hamming,
        "image_counts": counts,
        "within_collection_pair_counts": dict(Counter(pair[0].split("::")[0] for pair in within)),
        "cross_collection_pair_counts": dict(
            Counter(" <-> ".join(sorted((pair[0].split("::")[0], pair[1].split("::")[0]))) for pair in cross)
        ),
        "cross_collection_pairs": [{"a": a, "b": b, "hamming": d} for a, b, d in cross],
        "within_collection_pairs": [{"a": a, "b": b, "hamming": d} for a, b, d in within],
    }
    output = project_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"within={len(within)} cross={len(cross)} -> {output}")


if __name__ == "__main__":
    main()
