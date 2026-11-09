"""Build the LowerLimbFeetWound V3 external-evaluation manifest.

Pairs ``wound_main-NNNN.jpg`` with ``wound_mask-NNNN.jpg`` and records the
documented preprocessing decision for the masks whose size differs from their
image (224x224 masks for 331x331 images): the mask is **nearest-resized to the
image size at evaluation time**.  Raw files are never modified.

Masks are JPEG-compressed, so values other than 0/255 appear near edges; they
are binarized with threshold 128, the same rule used for FUSeg2021.

Images that are pHash near-duplicates of any FUSeg2021 image (train,
validation or test) are excluded, because an external set must not contain
training-distribution copies.

    python scripts/data/build_lowerlimb_external_manifest.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.data.fuseg import compute_sha256  # noqa: E402
from src.data.near_duplicates import (  # noqa: E402
    DEFAULT_MAX_HAMMING_DISTANCE,
    compute_phash_for_path,
    pairwise_hamming,
)

MANIFEST_VERSION = "lowerlimb-v3-external-v1"
INDEX_PATTERN = re.compile(r"-(\d+)\.[^.]+$")


def _index(path: Path) -> str | None:
    match = INDEX_PATTERN.search(path.name)
    return match.group(1) if match else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default="data/raw/LowerLimbFeetWound/V3/extracted")
    parser.add_argument("--fuseg-root", default="data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge")
    parser.add_argument("--output", default="data/manifests/lowerlimb_v3_external_manifest.json")
    parser.add_argument("--max-hamming", type=int, default=DEFAULT_MAX_HAMMING_DISTANCE)
    args = parser.parse_args()

    source_root = project_root / args.source_root
    images = {_index(path): path for path in sorted((source_root / "wound_main").iterdir()) if _index(path)}
    masks = {_index(path): path for path in sorted((source_root / "wound_mask").iterdir()) if _index(path)}
    unpaired = sorted(set(images) ^ set(masks))

    fuseg_root = project_root / args.fuseg_root
    fuseg_paths = sorted(path for split in ("train", "validation", "test") for path in (fuseg_root / split / "images").glob("*.png"))
    fuseg_hashes = [compute_phash_for_path(path) for path in fuseg_paths]

    records = []
    for index in sorted(set(images) & set(masks)):
        image_path, mask_path = images[index], masks[index]
        with Image.open(image_path) as image_file:
            image_size = image_file.size
        with Image.open(mask_path) as mask_file:
            mask_size = mask_file.size
        records.append({
            "dataset_name": "LowerLimbFeetWoundV3",
            "source_sample_id": index,
            "split": "external_test",
            "image_path": image_path.relative_to(project_root).as_posix(),
            "annotation_path": mask_path.relative_to(project_root).as_posix(),
            "checksum_sha256": compute_sha256(image_path),
            "annotation_checksum_sha256": compute_sha256(mask_path),
            "width": image_size[0],
            "height": image_size[1],
            "mask_width": mask_size[0],
            "mask_height": mask_size[1],
            "mask_resize_policy": "nearest_to_image_size" if mask_size != image_size else "none",
            "annotation_type": "wound_segmentation",
            "validation_status": "VALID",
            "issue_category": None,
            "phash": compute_phash_for_path(image_path),
        })

    distances = pairwise_hamming([record["phash"] for record in records] + fuseg_hashes)
    cross = distances[: len(records), len(records):]
    for row, record in enumerate(records):
        nearest = int(cross[row].min()) if cross.shape[1] else 64
        record["nearest_fuseg_hamming"] = nearest
        if nearest <= args.max_hamming:
            record["validation_status"] = "EXCLUDED"
            record["issue_category"] = "near_duplicate_of_fuseg2021"
            record["nearest_fuseg_image"] = fuseg_paths[int(cross[row].argmin())].relative_to(project_root).as_posix()
        record["phash"] = f"{record['phash']:016x}"

    valid = [record for record in records if record["validation_status"] == "VALID"]
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "dataset_name": "LowerLimbFeetWoundV3",
        "role": "external_evaluation_only",
        "source_root": args.source_root,
        "preprocessing_decisions": {
            "mask_size_mismatch": "Mask nearest-resized to the image size at evaluation time; raw files unchanged.",
            "mask_binarization": "JPEG mask values >= 128 are wound.",
            "fuseg_overlap": f"Images within pHash Hamming <= {args.max_hamming} of any FUSeg2021 image are excluded.",
        },
        "summary": {
            "paired_samples": len(records),
            "unpaired_indices": unpaired,
            "mask_size_mismatches": sum(record["mask_resize_policy"] != "none" for record in records),
            "excluded_near_duplicate_of_fuseg2021": len(records) - len(valid),
            "valid_external_samples": len(valid),
        },
        "samples": records,
    }
    output = project_root / args.output
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"] | {"unpaired_indices": len(unpaired)}, indent=2))


if __name__ == "__main__":
    main()
