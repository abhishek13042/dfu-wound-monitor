"""Perceptual-hash near-duplicate detection.

Exact SHA-256 checks only catch byte-identical files.  FUSeg2021 has no patient
IDs, and consecutive photographs of the same wound are visually near-identical
but differ byte-wise.  A 64-bit DCT perceptual hash (pHash) is stable under
re-encoding, small crops and mild exposure changes, so a small Hamming distance
between two hashes is strong evidence that two images show the same scene.

The grouping produced here is conservative: a false positive merges two
unrelated images into one group, which only makes a group-aware split stricter.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.fft import dctn

HASH_SIZE = 8
HIGHFREQ_FACTOR = 4
DEFAULT_MAX_HAMMING_DISTANCE = 8


def compute_phash(image: Image.Image) -> int:
    """Return a 64-bit DCT perceptual hash of ``image`` as a Python int."""

    side = HASH_SIZE * HIGHFREQ_FACTOR
    gray = image.convert("L").resize((side, side), resample=Image.Resampling.LANCZOS)
    coefficients = dctn(np.asarray(gray, dtype=np.float64), norm="ortho")
    low_frequency = coefficients[:HASH_SIZE, :HASH_SIZE]
    # The DC term encodes overall brightness and is excluded from the median.
    median = np.median(low_frequency.flatten()[1:])
    bits = (low_frequency > median).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def compute_phash_for_path(path: Path) -> int:
    """Decode an image file and return its pHash."""

    with Image.open(path) as image_file:
        image_file.load()
        return compute_phash(image_file)


def hamming_distance(first: int, second: int) -> int:
    """Number of differing bits between two 64-bit hashes."""

    return int(bin(int(first) ^ int(second)).count("1"))


def pairwise_hamming(hashes: Sequence[int]) -> np.ndarray:
    """Return the ``(N, N)`` Hamming-distance matrix for 64-bit hashes."""

    values = np.asarray([int(value) for value in hashes], dtype=np.uint64)
    if values.size == 0:
        return np.zeros((0, 0), dtype=np.int64)
    xor = np.bitwise_xor(values[:, None], values[None, :])
    return np.bitwise_count(xor).astype(np.int64)


def find_near_duplicate_pairs(
    hashes: dict[str, int],
    max_distance: int = DEFAULT_MAX_HAMMING_DISTANCE,
) -> list[tuple[str, str, int]]:
    """List ``(key_a, key_b, distance)`` pairs within ``max_distance``."""

    if not 0 <= max_distance <= 64:
        raise ValueError("max_distance must be in [0, 64]")
    keys = sorted(hashes)
    distances = pairwise_hamming([hashes[key] for key in keys])
    rows, columns = np.nonzero(np.triu(distances <= max_distance, k=1))
    return [(keys[row], keys[column], int(distances[row, column])) for row, column in zip(rows, columns)]


def group_near_duplicates(
    keys: Iterable[str],
    pairs: Iterable[tuple[str, str, int]],
) -> list[list[str]]:
    """Union-find connected components; every key appears in exactly one group."""

    parent: dict[str, str] = {key: key for key in keys}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for first, second, _ in pairs:
        root_first, root_second = find(first), find(second)
        if root_first != root_second:
            # Deterministic root choice keeps group membership order-independent.
            low, high = sorted((root_first, root_second))
            parent[high] = low

    groups: dict[str, list[str]] = {}
    for key in parent:
        groups.setdefault(find(key), []).append(key)
    return sorted((sorted(members) for members in groups.values()), key=lambda group: group[0])
