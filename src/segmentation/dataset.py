"""Reproducible PyTorch input pipeline for manifest-backed wound masks.

The dataset reads split assignments from the Phase 01 manifest.  It never
discovers files or creates a new split during training.  Spatial operations
that affect geometry are applied to the image and mask with the same sampled
parameters.
"""

from __future__ import annotations

import json
import logging
import math
import random
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

LOGGER = logging.getLogger(__name__)


def resolve_manifest_path(path_value: Optional[str], manifest_path: str) -> Path:
    """Resolve a manifest path relative to the repository containing the manifest.

    Relative paths are preferred.  Legacy absolute Windows paths are accepted
    only when their ``data/...`` suffix exists in the current repository; this
    keeps old manifests inspectable without silently accepting a missing path.
    """

    if not path_value:
        return Path("")

    manifest_file = Path(manifest_path).resolve()
    candidate_roots = [manifest_file.parent, *manifest_file.parents]
    normalized_value = str(path_value).replace("\\", "/")
    windows_parts = PureWindowsPath(normalized_value).parts
    posix_parts = PurePosixPath(normalized_value).parts
    path_parts = windows_parts if len(windows_parts) > 1 else posix_parts

    direct_path = Path(path_value)
    # A manifest path is authoritative.  Do not let an unrelated file with
    # the same relative name in the caller's working directory win.
    if direct_path.is_absolute() or PureWindowsPath(normalized_value).is_absolute():
        if direct_path.exists():
            return direct_path
    else:
        # Manifests used by tests and portable exports commonly store paths
        # relative to the directory containing the manifest.
        manifest_relative = manifest_file.parent / direct_path
        if manifest_relative.exists():
            return manifest_relative

    if "data" in path_parts:
        data_index = path_parts.index("data")
        relative_data_path = Path(*path_parts[data_index:])
        # FUSeg manifests store project-relative paths such as data/raw/... .
        # Prefer the repository-level candidate over data/manifests/... so a
        # coincidentally named path cannot shadow the source tree.
        for root in reversed(candidate_roots):
            candidate = root / relative_data_path
            if candidate.exists():
                return candidate

    if not direct_path.is_absolute():
        for root in candidate_roots:
            candidate = root / direct_path
            if candidate.exists():
                return candidate

    return direct_path


def load_manifest_samples(
    manifest_path: str,
    split: str,
    allowed_annotation_types: Optional[List[str]] = None,
    data_root: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load only valid, annotated samples assigned to ``split``.

    The loader preserves the manifest's official split and excludes records
    marked ``INVALID`` or ``QUARANTINED``.  Public FUSeg test images have the
    ``unlabeled_test`` annotation type and therefore do not enter this
    supervised dataset.
    """

    if split not in {"train", "val", "test"}:
        raise ValueError(f"Invalid split '{split}'. Must be one of: {{'train', 'val', 'test'}}")
    if allowed_annotation_types is None:
        allowed_annotation_types = ["wound_segmentation"]

    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    with manifest_file.open("r", encoding="utf-8") as manifest_handle:
        manifest_data = json.load(manifest_handle)

    selected_samples: List[Dict[str, Any]] = []
    for sample in manifest_data.get("samples", []):
        if sample.get("split") != split:
            continue
        if sample.get("validation_status") != "VALID":
            continue
        if sample.get("annotation_type") not in allowed_annotation_types:
            continue
        normalized_sample = dict(sample)
        for field in ("image_path", "annotation_path"):
            value = sample.get(field)
            if not value:
                raise ValueError(f"Valid supervised sample '{sample.get('source_sample_id')}' is missing {field}")
            if data_root is None:
                resolved = resolve_manifest_path(value, manifest_path)
            else:
                source_root = PurePosixPath(manifest_data.get("source_root", ""))
                if not manifest_data.get("source_root"):
                    raise ValueError("Remapping data_root requires manifest.source_root")
                try:
                    relative = PurePosixPath(str(value).replace("\\", "/")).relative_to(source_root)
                except ValueError as error:
                    raise ValueError(f"{field} is outside manifest.source_root: {value}") from error
                if ".." in relative.parts:
                    raise ValueError(f"{field} must not traverse outside data_root")
                resolved = Path(data_root).resolve() / Path(*relative.parts)
            normalized_sample[field] = str(resolved)
        selected_samples.append(normalized_sample)

    LOGGER.info("Manifest loaded: split=%s, annotated valid samples=%d", split, len(selected_samples))
    return selected_samples


def _validate_normalization(mean: List[float], std: List[float]) -> None:
    if len(mean) != 3 or len(std) != 3:
        raise ValueError("normalize_mean and normalize_std must each contain three values")
    if not all(math.isfinite(value) for value in [*mean, *std]):
        raise ValueError("Normalization values must be finite")
    if any(value <= 0 for value in std):
        raise ValueError("normalize_std values must be positive")


def preprocess_image(
    image_pil: Image.Image,
    target_height: int,
    target_width: int,
    normalize_mean: List[float],
    normalize_std: List[float],
) -> torch.Tensor:
    """Convert an image to normalized ``float32`` RGB ``(3,H,W)`` tensor."""

    if target_height <= 0 or target_width <= 0:
        raise ValueError("target_height and target_width must be positive")
    _validate_normalization(normalize_mean, normalize_std)
    image_rgb = image_pil.convert("RGB")
    image_resized = image_rgb.resize(
        (target_width, target_height), resample=Image.Resampling.BILINEAR
    )
    image_array = np.asarray(image_resized, dtype=np.float32) / 255.0
    mean_array = np.asarray(normalize_mean, dtype=np.float32).reshape(1, 1, 3)
    std_array = np.asarray(normalize_std, dtype=np.float32).reshape(1, 1, 3)
    image_normalized = (image_array - mean_array) / std_array
    return torch.from_numpy(np.transpose(image_normalized, (2, 0, 1)).copy())


def preprocess_mask(
    mask_pil: Image.Image,
    target_height: int,
    target_width: int,
    threshold: int = 128,
) -> torch.Tensor:
    """Convert a source mask to strict binary ``float32`` ``(1,H,W)`` tensor."""

    if target_height <= 0 or target_width <= 0:
        raise ValueError("target_height and target_width must be positive")
    if not 1 <= threshold <= 255:
        raise ValueError("mask threshold must be in [1, 255]")
    mask_gray = mask_pil.convert("L").resize(
        (target_width, target_height), resample=Image.Resampling.NEAREST
    )
    binary_mask = (np.asarray(mask_gray, dtype=np.uint8) >= threshold).astype(np.float32)
    return torch.from_numpy(binary_mask[None, :, :].copy())


def apply_random_horizontal_flip(
    image_tensor: torch.Tensor,
    mask_tensor: torch.Tensor,
    flip_probability: float,
    random_source: Optional[random.Random] = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Apply the same horizontal flip decision to image and mask."""

    if not 0.0 <= flip_probability <= 1.0:
        raise ValueError("flip_probability must be in [0, 1]")
    random_source = random_source or random
    if random_source.random() < flip_probability:
        return torch.flip(image_tensor, dims=[-1]), torch.flip(mask_tensor, dims=[-1])
    return image_tensor, mask_tensor


def apply_random_vertical_flip(
    image_tensor: torch.Tensor,
    mask_tensor: torch.Tensor,
    flip_probability: float,
    random_source: Optional[random.Random] = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Apply the same vertical flip decision to image and mask."""

    if not 0.0 <= flip_probability <= 1.0:
        raise ValueError("flip_probability must be in [0, 1]")
    random_source = random_source or random
    if random_source.random() < flip_probability:
        return torch.flip(image_tensor, dims=[-2]), torch.flip(mask_tensor, dims=[-2])
    return image_tensor, mask_tensor


class WoundSegmentationDataset(Dataset[Tuple[torch.Tensor, torch.Tensor, str]]):
    """Manifest-backed supervised segmentation dataset."""

    def __init__(
        self,
        samples: List[Dict[str, Any]],
        input_height: int,
        input_width: int,
        normalize_mean: List[float],
        normalize_std: List[float],
        mask_threshold: int = 128,
        is_training: bool = False,
        horizontal_flip_prob: float = 0.5,
        vertical_flip_prob: float = 0.0,
        random_seed: int = 42,
        require_annotations: bool = True,
        expected_source_mask_values: Optional[Sequence[int]] = (0, 255),
        augmenter: Optional[Callable[[torch.Tensor, torch.Tensor, torch.Generator], Tuple[torch.Tensor, torch.Tensor]]] = None,
    ) -> None:
        self.samples = list(samples)
        # SPEC-02-03 synchronized augmentation; replaces the flip-only path
        # for training samples when provided.
        self.augmenter = augmenter
        self.input_height = input_height
        self.input_width = input_width
        self.normalize_mean = list(normalize_mean)
        self.normalize_std = list(normalize_std)
        self.mask_threshold = mask_threshold
        self.is_training = is_training
        self.horizontal_flip_prob = horizontal_flip_prob
        self.vertical_flip_prob = vertical_flip_prob
        self.random_seed = random_seed
        self._epoch = torch.zeros((), dtype=torch.int64).share_memory_()
        self.require_annotations = require_annotations
        self.expected_source_mask_values = (
            {int(value) for value in expected_source_mask_values}
            if expected_source_mask_values is not None
            else None
        )
        if self.expected_source_mask_values is not None and not self.expected_source_mask_values:
            raise ValueError("expected_source_mask_values cannot be empty")
        if self.expected_source_mask_values is not None and any(
            value < 0 or value > 255 for value in self.expected_source_mask_values
        ):
            raise ValueError("expected_source_mask_values must contain byte values")
        _validate_normalization(self.normalize_mean, self.normalize_std)
        if type(input_height) is not int or type(input_width) is not int or min(input_height, input_width) <= 0:
            raise ValueError("input_height and input_width must be positive integers")
        if not 1 <= mask_threshold <= 255:
            raise ValueError("mask_threshold must be in [1, 255]")
        if not 0 <= horizontal_flip_prob <= 1 or not 0 <= vertical_flip_prob <= 1:
            raise ValueError("Flip probabilities must be in [0, 1]")
        if not require_annotations:
            raise ValueError("WoundSegmentationDataset is supervised and requires annotations")
        self._validate_file_paths()

    def _validate_file_paths(self) -> None:
        missing: List[str] = []
        for sample in self.samples:
            sample_id = sample.get("source_sample_id", "unknown")
            if sample.get("validation_status") not in (None, "VALID"):
                raise ValueError(f"{sample_id}: invalid manifest validation_status {sample.get('validation_status')!r}")
            image_path = Path(sample.get("image_path", ""))
            annotation_value = sample.get("annotation_path")
            annotation_path = Path(annotation_value) if annotation_value else None
            if not image_path.is_file():
                missing.append(f"{sample_id}: image missing: {image_path}")
            if self.require_annotations and (annotation_path is None or not annotation_path.is_file()):
                missing.append(f"{sample_id}: annotation missing: {annotation_path}")
        if missing:
            preview = "\n".join(missing[:20])
            suffix = "" if len(missing) <= 20 else f"\n... and {len(missing) - 20} more"
            raise FileNotFoundError(f"Invalid manifest paths ({len(missing)}):\n{preview}{suffix}")

    def set_epoch(self, epoch: int) -> None:
        """Set the epoch used by deterministic per-sample augmentation."""

        self._epoch.fill_(int(epoch))

    @property
    def epoch(self) -> int:
        """Shared epoch is visible to persistent DataLoader worker copies."""
        return int(self._epoch.item())

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        if not 0 <= index < len(self.samples):
            raise IndexError(f"Sample index {index} is outside dataset length {len(self.samples)}")
        sample = self.samples[index]
        sample_id = str(sample.get("source_sample_id", f"sample_{index}"))
        image_path = Path(sample["image_path"])
        annotation_value = sample.get("annotation_path")
        if self.require_annotations and not annotation_value:
            raise RuntimeError(f"Sample '{sample_id}' has no annotation_path")
        if not annotation_value:
            raise RuntimeError("WoundSegmentationDataset requires annotations for every sample")
        annotation_path = Path(annotation_value)
        try:
            with Image.open(image_path) as image_file:
                image_file.load()
                image_pil = image_file.copy()
            with Image.open(annotation_path) as mask_file:
                mask_file.load()
                mask_pil = mask_file.copy()
        except Exception as error:
            raise RuntimeError(f"Failed to decode sample '{sample_id}': {error}") from error

        expected_size = (sample.get("width"), sample.get("height"))
        if expected_size[0] is not None and expected_size[1] is not None:
            declared_size = (int(expected_size[0]), int(expected_size[1]))
            if image_pil.size != declared_size:
                raise RuntimeError(
                    f"Sample '{sample_id}' image size {image_pil.size} does not match "
                    f"manifest size {declared_size}"
                )
        if image_pil.size != mask_pil.size:
            raise RuntimeError(
                f"Sample '{sample_id}' image/mask size mismatch: "
                f"{image_pil.size} vs {mask_pil.size}"
            )
        raw_mask_array = np.asarray(mask_pil)
        if raw_mask_array.ndim == 3 and not np.all(raw_mask_array == raw_mask_array[:, :, :1]):
            raise RuntimeError(f"Sample '{sample_id}' contains a non-grayscale mask")
        source_mask_array = raw_mask_array[:, :, 0] if raw_mask_array.ndim == 3 else raw_mask_array
        if self.expected_source_mask_values is not None:
            observed_values = {int(value) for value in np.unique(source_mask_array)}
            if not observed_values.issubset(self.expected_source_mask_values):
                raise RuntimeError(
                    f"Sample '{sample_id}' contains invalid source mask values "
                    f"{sorted(observed_values)}; expected a subset of "
                    f"{sorted(self.expected_source_mask_values)}"
                )

        mask_tensor = preprocess_mask(
            mask_pil,
            self.input_height,
            self.input_width,
            self.mask_threshold,
        )
        if self.is_training and self.augmenter is not None:
            image_unit = preprocess_image(
                image_pil, self.input_height, self.input_width, [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
            )
            generator = torch.Generator()
            generator.manual_seed(self.random_seed + self.epoch * max(len(self), 1) + index)
            image_unit, mask_tensor = self.augmenter(image_unit, mask_tensor, generator)
            mean = torch.tensor(self.normalize_mean, dtype=torch.float32).view(3, 1, 1)
            std = torch.tensor(self.normalize_std, dtype=torch.float32).view(3, 1, 1)
            image_tensor = (image_unit - mean) / std
        else:
            image_tensor = preprocess_image(
                image_pil,
                self.input_height,
                self.input_width,
                self.normalize_mean,
                self.normalize_std,
            )

        if self.is_training and self.augmenter is None:
            # A local generator avoids dependence on global random state and
            # makes a sample's transform reproducible for a seed and epoch.
            source = random.Random(self.random_seed + self.epoch * max(len(self), 1) + index)
            image_tensor, mask_tensor = apply_random_horizontal_flip(
                image_tensor, mask_tensor, self.horizontal_flip_prob, source
            )
            image_tensor, mask_tensor = apply_random_vertical_flip(
                image_tensor, mask_tensor, self.vertical_flip_prob, source
            )

        unique_mask_values = torch.unique(mask_tensor)
        if not torch.all((unique_mask_values == 0) | (unique_mask_values == 1)):
            raise RuntimeError(f"Sample '{sample_id}' produced a non-binary mask")
        return image_tensor, mask_tensor, sample_id


def _seed_worker(worker_id: int) -> None:
    """Seed Python and NumPy in each DataLoader worker."""

    worker_seed = torch.initial_seed() % (2**32)
    random.seed(worker_seed)
    np.random.seed(worker_seed)


def _make_loader(
    dataset: WoundSegmentationDataset,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
    seed: int,
    pin_memory: bool,
    persistent_workers: bool,
) -> DataLoader:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if num_workers < 0:
        raise ValueError("num_workers must be non-negative")
    if persistent_workers and num_workers == 0:
        raise ValueError("persistent_workers requires num_workers > 0")
    generator = torch.Generator()
    generator.manual_seed(seed)
    loader_kwargs: Dict[str, Any] = {
        "dataset": dataset,
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": num_workers,
        "drop_last": False,
        "pin_memory": pin_memory,
        "worker_init_fn": _seed_worker,
        "generator": generator,
    }
    if num_workers > 0:
        loader_kwargs["persistent_workers"] = persistent_workers
        loader_kwargs["prefetch_factor"] = 2
    return DataLoader(**loader_kwargs)


def create_dataloaders(
    manifest_path: str,
    input_height: int,
    input_width: int,
    normalize_mean: List[float],
    normalize_std: List[float],
    mask_threshold: int,
    batch_size: int,
    horizontal_flip_prob: float,
    num_workers: int = 0,
    vertical_flip_prob: float = 0.0,
    random_seed: int = 42,
    pin_memory: bool = False,
    persistent_workers: bool = False,
    test_batch_size: int = 1,
    expected_source_mask_values: Optional[Sequence[int]] = (0, 255),
    data_root: Optional[str] = None,
    include_test: bool = True,
) -> Tuple[DataLoader, DataLoader, Optional[DataLoader]]:
    """Create train/validation loaders and an optional labeled test loader.

    FUSeg2021 public test images are intentionally returned as ``None`` here
    because no usable ground-truth masks are distributed.
    """

    train_samples = load_manifest_samples(manifest_path, split="train", data_root=data_root)
    val_samples = load_manifest_samples(manifest_path, split="val", data_root=data_root)
    test_samples = load_manifest_samples(manifest_path, split="test", data_root=data_root) if include_test else []
    if not train_samples or not val_samples:
        raise RuntimeError(
            f"Manifest must provide non-empty annotated train and val splits; "
            f"got train={len(train_samples)}, val={len(val_samples)}"
        )

    train_dataset = WoundSegmentationDataset(
        train_samples,
        input_height,
        input_width,
        normalize_mean,
        normalize_std,
        mask_threshold,
        is_training=True,
        horizontal_flip_prob=horizontal_flip_prob,
        vertical_flip_prob=vertical_flip_prob,
        random_seed=random_seed,
        expected_source_mask_values=expected_source_mask_values,
    )
    val_dataset = WoundSegmentationDataset(
        val_samples,
        input_height,
        input_width,
        normalize_mean,
        normalize_std,
        mask_threshold,
        is_training=False,
        horizontal_flip_prob=0.0,
        vertical_flip_prob=0.0,
        random_seed=random_seed,
        expected_source_mask_values=expected_source_mask_values,
    )
    test_loader: Optional[DataLoader] = None
    if test_samples:
        test_dataset = WoundSegmentationDataset(
            test_samples,
            input_height,
            input_width,
            normalize_mean,
            normalize_std,
            mask_threshold,
            is_training=False,
            require_annotations=True,
            expected_source_mask_values=expected_source_mask_values,
        )
        test_loader = _make_loader(
            test_dataset,
            test_batch_size,
            shuffle=False,
            num_workers=num_workers,
            seed=random_seed + 2,
            pin_memory=pin_memory,
            persistent_workers=persistent_workers,
        )

    train_loader = _make_loader(
        train_dataset,
        batch_size,
        shuffle=True,
        num_workers=num_workers,
        seed=random_seed,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
    )
    val_loader = _make_loader(
        val_dataset,
        batch_size,
        shuffle=False,
        num_workers=num_workers,
        seed=random_seed + 1,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
    )
    LOGGER.info(
        "DataLoaders created: train=%d, val=%d, labeled_test=%s",
        len(train_dataset),
        len(val_dataset),
        len(test_samples) if test_samples else "none",
    )
    return train_loader, val_loader, test_loader
