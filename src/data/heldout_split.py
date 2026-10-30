"""Derive a held-out evaluation manifest from the official FUSeg2021 manifest.

FUSeg2021 public test masks are not released, so the official manifest has no
labeled test split.  When the official validation split is also used for model
selection, nothing is left for unbiased evaluation.  This module derives the
SPEC-02-03 split without touching raw data:

* official ``validation`` -> ``test``: held out, evaluated once at the end
* official ``train``      -> ``train`` + ``val`` (internal validation, seeded)
* official unlabeled test -> ``unlabeled_test`` (never used for supervision)

Two leakage guards apply because FUSeg2021 has no patient identifiers:

1. The internal validation split is group-aware.  Near-duplicate images
   (pHash Hamming distance <= threshold) always land on the same side.
2. Official-train images that are near-duplicates of a held-out test image are
   quarantined and are not used for training or validation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any

from src.data.near_duplicates import (
    DEFAULT_MAX_HAMMING_DISTANCE,
    find_near_duplicate_pairs,
    group_near_duplicates,
)

HELDOUT_MANIFEST_VERSION = "fuseg2021-heldout-v1"
HELDOUT_SPLIT_POLICY = (
    "SPEC-02-03 held-out policy: official validation is the held-out test split; "
    "internal validation is a seeded, near-duplicate-group-aware subset of official train"
)


def sample_key(record: dict[str, Any]) -> str:
    """Stable identifier that is unique across official splits."""

    return f"{record['official_split']}/{record['source_sample_id']}"


def _is_labeled_valid(record: dict[str, Any]) -> bool:
    return record.get("validation_status") == "VALID" and record.get("annotation_type") == "wound_segmentation"


def _select_internal_val_groups(
    groups: list[list[str]],
    empty_keys: set,
    fraction: float,
    seed: int,
) -> set:
    """Pick whole groups until each stratum reaches ``fraction`` of its images.

    Groups are stratified by whether they contain an empty-mask image so the
    rare empty case is represented in internal validation.
    """

    rng = random.Random(seed)
    selected: set = set()
    for has_empty in (True, False):
        stratum = [group for group in groups if any(key in empty_keys for key in group) == has_empty]
        rng.shuffle(stratum)
        target = round(fraction * sum(len(group) for group in stratum))
        count = 0
        for group in stratum:
            if count >= target:
                break
            # Skip a group that would overshoot by more than half its size.
            if count + len(group) - target > len(group) / 2 and count > 0:
                continue
            selected.update(group)
            count += len(group)
    return selected


def derive_heldout_manifest(
    manifest: dict[str, Any],
    phashes: dict[str, int],
    internal_val_fraction: float = 0.15,
    seed: int = 42,
    max_hamming_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(heldout_manifest, split_report)``.

    ``phashes`` maps :func:`sample_key` to a 64-bit pHash for every VALID
    labeled record.  The input manifest is not modified.
    """

    if not 0.0 < internal_val_fraction < 0.5:
        raise ValueError("internal_val_fraction must be in (0, 0.5)")
    if manifest.get("dataset_name") != "FUSeg2021":
        raise ValueError("Held-out derivation is defined for the FUSeg2021 manifest only")

    derived = copy.deepcopy(manifest)
    records: list[dict[str, Any]] = derived["samples"]
    labeled = [record for record in records if _is_labeled_valid(record)]
    missing = [sample_key(record) for record in labeled if sample_key(record) not in phashes]
    if missing:
        raise ValueError(f"Missing pHash for {len(missing)} labeled samples, e.g. {missing[:3]}")

    labeled_hashes = {sample_key(record): phashes[sample_key(record)] for record in labeled}
    pairs = find_near_duplicate_pairs(labeled_hashes, max_hamming_distance)
    groups = group_near_duplicates(labeled_hashes, pairs)

    official_split_by_key = {sample_key(record): record["official_split"] for record in labeled}
    # Guard 2: train images in a group that also contains a test image.
    train_near_test: set[str] = set()
    for group in groups:
        if any(official_split_by_key[key] == "validation" for key in group):
            train_near_test.update(key for key in group if official_split_by_key[key] == "train")

    train_groups = [
        [key for key in group if key not in train_near_test]
        for group in groups
        if all(official_split_by_key[key] == "train" for key in group)
    ]
    train_groups = [group for group in train_groups if group]
    empty_keys = {
        sample_key(record) for record in labeled if record.get("quality", {}).get("mask_empty")
    }
    internal_val_keys = _select_internal_val_groups(train_groups, empty_keys, internal_val_fraction, seed)

    group_id_by_key = {key: index for index, group in enumerate(groups) for key in group}
    for record in records:
        key = sample_key(record)
        record["near_duplicate_group"] = group_id_by_key.get(key)
        if record["official_split"] == "test":
            record["split"] = "unlabeled_test"
            record["heldout_role"] = "unlabeled_public_test"
        elif not _is_labeled_valid(record):
            record["heldout_role"] = "excluded"
        elif record["official_split"] == "validation":
            record["split"] = "test"
            record["heldout_role"] = "heldout_test"
        elif key in train_near_test:
            record["split"] = "excluded"
            record["validation_status"] = "QUARANTINED"
            record["issue_category"] = "near_duplicate_of_heldout_test"
            record["heldout_role"] = "excluded"
        elif key in internal_val_keys:
            record["split"] = "val"
            record["heldout_role"] = "internal_val"
        else:
            record["split"] = "train"
            record["heldout_role"] = "train"

    usable = [record for record in records if _is_labeled_valid(record)]
    counts = {
        split: sum(record["split"] == split for record in usable) for split in ("train", "val", "test")
    }
    empty_counts = {
        split: sum(record["split"] == split and bool(record.get("quality", {}).get("mask_empty")) for record in usable)
        for split in ("train", "val", "test")
    }
    multi_member_groups = [group for group in groups if len(group) > 1]
    parent_digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()

    derived["manifest_version"] = HELDOUT_MANIFEST_VERSION
    derived["split_policy"] = HELDOUT_SPLIT_POLICY
    derived["parent_manifest_sha256"] = parent_digest
    derived["heldout_split_parameters"] = {
        "internal_val_fraction": internal_val_fraction,
        "seed": seed,
        "near_duplicate_method": "64-bit DCT pHash",
        "max_hamming_distance": max_hamming_distance,
    }
    derived["split_summary"] = {
        **derived.get("split_summary", {}),
        "split_mode": "HELDOUT_OFFICIAL_VALIDATION_AS_TEST",
        "train_samples": counts["train"],
        "val_samples": counts["val"],
        "test_samples": counts["test"],
        "empty_mask_samples": empty_counts,
        "unlabeled_public_test_samples": sum(record["split"] == "unlabeled_test" for record in records),
        "quarantined_near_duplicate_of_test": len(train_near_test),
    }
    report = {
        "manifest_version": HELDOUT_MANIFEST_VERSION,
        "parent_manifest_sha256": parent_digest,
        "parameters": derived["heldout_split_parameters"],
        "counts": counts,
        "empty_mask_counts": empty_counts,
        "near_duplicate_pairs": len(pairs),
        "near_duplicate_groups_with_multiple_members": len(multi_member_groups),
        "largest_group_size": max((len(group) for group in groups), default=0),
        "train_quarantined_near_duplicate_of_test": sorted(train_near_test),
        "cross_split_groups": [
            group
            for group in multi_member_groups
            if len({official_split_by_key[key] for key in group}) > 1
        ],
        "pairs": [
            {"a": first, "b": second, "hamming": distance} for first, second, distance in pairs
        ],
    }
    return derived, report
