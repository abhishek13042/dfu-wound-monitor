"""
Baseline Segmentation Dataset Interface — DFU-WoundMonitor.

Spec: P02-S02 — Baseline Preprocessing and Dataset Interface.

This module bridges Phase 01 manifests to the PyTorch training loop.
It loads images and masks from the paths recorded in the Phase 01 manifest,
applies the correct preprocessing per split (train vs val/test), and
returns batches ready for the model.

IMPORTANT DATA FLOW:
    Phase 01 manifest (JSON)
        → load_manifest_samples()        [reads from file, filters by split]
        → WoundSegmentationDataset       [PyTorch Dataset object]
        → DataLoader                     [produces batches for training/eval]

Every preprocessing step is explicitly documented below.

Coding Style: Beginner-Understandable Python
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset


# ============================================================
# STEP 1: Load samples from Phase 01 manifest
# ============================================================

def load_manifest_samples(
    manifest_path: str,
    split: str,
    allowed_annotation_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Load validated samples for a given split from the Phase 01 manifest.

    This function is the bridge between Phase 01 outputs and Phase 02 training.
    It DOES NOT rediscover or reshuffle data — it reads exactly the splits
    recorded in the manifest (REQ-P02-S02-001, REQ-P02-S02-009).

    Inputs:
        manifest_path: Path to dataset_manifest.json (Phase 01 output).
        split: One of 'train', 'val', 'test'.
        allowed_annotation_types: If provided, only load samples whose
            annotation_type is in this list. Defaults to ['wound_segmentation'].

    Outputs:
        List of sample dictionaries for the requested split.
        Only VALID samples are returned (REQ-P02-S02-008).

    Raises:
        FileNotFoundError: If manifest_path does not exist.
        ValueError: If split is not recognized.
    """
    valid_splits = {"train", "val", "test"}
    if split not in valid_splits:
        raise ValueError(
            f"Invalid split '{split}'. Must be one of: {valid_splits}"
        )

    if allowed_annotation_types is None:
        # Default to segmentation only — this baseline focuses on segmentation
        allowed_annotation_types = ["wound_segmentation"]

    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise FileNotFoundError(
            f"Manifest file not found: {manifest_path}. "
            "Run the Phase 01 pipeline first to generate the manifest."
        )

    # Read the manifest JSON file
    with open(manifest_file, "r", encoding="utf-8") as manifest_handle:
        manifest_data = json.load(manifest_handle)

    all_samples = manifest_data.get("samples", [])

    # Filter: keep only samples that match the requested split,
    # are VALID, and have a supported annotation type.
    # Phase 01 invalid samples must not enter training (REQ-P02-S02-008).
    selected_samples = []

    for sample in all_samples:
        sample_split = sample.get("split", "")
        sample_validation_status = sample.get("validation_status", "")
        sample_annotation_type = sample.get("annotation_type", "")

        # Check split match
        if sample_split != split:
            continue

        # Check validation status — only VALID samples allowed
        if sample_validation_status != "VALID":
            print(
                f"  [SKIP] Sample '{sample.get('source_sample_id')}' "
                f"has validation_status='{sample_validation_status}' — excluded."
            )
            continue

        # Check annotation type is supported for this task
        if sample_annotation_type not in allowed_annotation_types:
            print(
                f"  [SKIP] Sample '{sample.get('source_sample_id')}' "
                f"has annotation_type='{sample_annotation_type}' — excluded from segmentation task."
            )
            continue

        selected_samples.append(sample)

    print(
        f"Manifest loaded: split='{split}' -> {len(selected_samples)} valid samples "
        f"(out of {len(all_samples)} total in manifest)."
    )

    return selected_samples


# ============================================================
# STEP 2: Preprocessing helpers
# ============================================================

def preprocess_image(
    image_pil: Image.Image,
    target_height: int,
    target_width: int,
    normalize_mean: List[float],
    normalize_std: List[float],
) -> torch.Tensor:
    """
    Convert a PIL Image to a normalized PyTorch tensor.

    Preprocessing steps (REQ-P02-S02-003):
        1. Convert to RGB (ensures 3 channels regardless of source format).
        2. Resize to (target_height, target_width) using bilinear interpolation.
        3. Convert pixel values from [0, 255] uint8 to [0.0, 1.0] float32.
        4. Normalize: subtract mean, divide by std, per channel.

    Inputs:
        image_pil: PIL Image object loaded from disk.
        target_height: Target height in pixels.
        target_width: Target width in pixels.
        normalize_mean: Per-channel mean for normalization (list of 3 floats).
        normalize_std: Per-channel std for normalization (list of 3 floats).

    Outputs:
        Tensor of shape (3, target_height, target_width), dtype=float32.

    Tensor shape documentation (REQ-P02-S02-006):
        Shape: (C=3, H=target_height, W=target_width)
        Dtype: torch.float32
        Value range: approximately [-2, 2] after normalization
    """
    # Step 1: Ensure RGB (3 channels)
    image_rgb = image_pil.convert("RGB")

    # Step 2: Resize to target resolution
    image_resized = image_rgb.resize((target_width, target_height), Image.BILINEAR)

    # Step 3: Convert to numpy float array in [0, 1]
    image_array = np.array(image_resized, dtype=np.float32) / 255.0

    # Step 4: Normalize each channel
    # image_array shape: (H, W, C) — height, width, channels
    mean_array = np.array(normalize_mean, dtype=np.float32)  # shape: (3,)
    std_array = np.array(normalize_std, dtype=np.float32)     # shape: (3,)

    # Broadcasting: (H, W, C) - (3,) = (H, W, C)
    image_normalized = (image_array - mean_array) / std_array

    # Convert from (H, W, C) to (C, H, W) — PyTorch convention
    # np.transpose(array, (2, 0, 1)) moves the channel axis from last to first
    image_chw = np.transpose(image_normalized, (2, 0, 1))

    return torch.tensor(image_chw, dtype=torch.float32)


def preprocess_mask(
    mask_pil: Image.Image,
    target_height: int,
    target_width: int,
    threshold: int = 128,
) -> torch.Tensor:
    """
    Convert a binary mask PIL Image to a PyTorch float tensor.

    The DFUC2022 masks use pixel values {0, 255}.
    We resize then threshold to get a clean binary mask {0.0, 1.0}.

    Preprocessing steps (REQ-P02-S02-003):
        1. Convert to grayscale (L mode) — masks are single-channel.
        2. Resize to (target_height, target_width) using NEAREST interpolation
           to avoid interpolation artifacts on binary masks.
        3. Threshold: pixels >= threshold → 1.0 (wound), else → 0.0 (background).

    Inputs:
        mask_pil: PIL Image of binary mask ({0, 255}).
        target_height: Target height in pixels.
        target_width: Target width in pixels.
        threshold: Binarization threshold (default: 128).

    Outputs:
        Tensor of shape (1, target_height, target_width), dtype=float32.
        Values are exactly {0.0, 1.0}.

    Tensor shape documentation (REQ-P02-S02-006):
        Shape: (C=1, H=target_height, W=target_width)
        Dtype: torch.float32
        Values: {0.0 = background, 1.0 = wound}

    IMPORTANT: We use NEAREST interpolation for masks, NOT bilinear.
    Reason: Bilinear interpolation on a binary {0, 255} mask would create
    intermediate gray pixel values (e.g., 127) which are ambiguous and
    introduce artificial uncertainty at boundaries.
    NEAREST interpolation preserves the original binary labels.
    """
    # Step 1: Convert to grayscale (single channel)
    mask_gray = mask_pil.convert("L")

    # Step 2: Resize using NEAREST to preserve binary label integrity
    mask_resized = mask_gray.resize((target_width, target_height), Image.NEAREST)

    # Step 3: Convert to numpy array
    mask_array = np.array(mask_resized, dtype=np.float32)

    # Step 4: Threshold to strict binary {0.0, 1.0}
    # Pixels >= threshold are wound (1.0), others are background (0.0)
    binary_mask = (mask_array >= threshold).astype(np.float32)

    # Add channel dimension: (H, W) → (1, H, W)
    binary_mask_with_channel = binary_mask[np.newaxis, :, :]  # shape: (1, H, W)

    return torch.tensor(binary_mask_with_channel, dtype=torch.float32)


# ============================================================
# STEP 3: Augmentation helpers (train-only)
# ============================================================

def apply_random_horizontal_flip(
    image_tensor: torch.Tensor,
    mask_tensor: torch.Tensor,
    flip_probability: float,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Apply random horizontal flip consistently to both image and mask.

    WHY consistent transforms matter (REQ-P02-S02-004, REQ-P02-S02-007):
        If we flip the image but NOT the mask, the wound location in the image
        will be on the opposite side from the mask label → the model learns
        from corrupted supervision signals.
        ALWAYS apply the same spatial transform to both image and mask.

    Inputs:
        image_tensor: Image tensor (C, H, W).
        mask_tensor: Mask tensor (1, H, W).
        flip_probability: Probability of flipping (0.0 to 1.0).

    Outputs:
        Tuple of (image_tensor, mask_tensor) — either both flipped or both unchanged.
    """
    if random.random() < flip_probability:
        # torch.flip(tensor, dims) reverses the specified dimension
        # dim=2 is the width dimension (C, H, W) — horizontal flip
        image_flipped = torch.flip(image_tensor, dims=[2])
        mask_flipped = torch.flip(mask_tensor, dims=[2])
        return image_flipped, mask_flipped

    return image_tensor, mask_tensor


# ============================================================
# STEP 4: PyTorch Dataset class
# ============================================================

class WoundSegmentationDataset(Dataset):
    """
    PyTorch Dataset for wound segmentation from Phase 01 manifests.

    This class bridges the Phase 01 data foundation to the PyTorch
    training pipeline. It loads images and masks from paths recorded
    in the Phase 01 manifest, applies preprocessing, and returns
    tensors ready for the model.

    WHAT THIS CLASS DOES:
        - Reads image paths and annotation paths from the Phase 01 manifest
        - Applies preprocessing to normalize images for the model
        - Applies augmentations to training samples only (REQ-P02-S02-004)
        - Ensures image/mask spatial alignment is preserved (REQ-P02-S02-002)

    WHAT THIS CLASS DOES NOT DO:
        - Reshuffle or re-split samples (that was done in Phase 01)
        - Include invalid samples (they were filtered in load_manifest_samples)

    Parameters:
        samples: List of sample dicts from load_manifest_samples().
        input_height: Target image height.
        input_width: Target image width.
        normalize_mean: Normalization mean per channel.
        normalize_std: Normalization std per channel.
        mask_threshold: Threshold for binarizing masks.
        is_training: If True, apply training augmentations.
        horizontal_flip_prob: Probability of horizontal flip augmentation.
    """

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
    ):
        self.samples = samples
        self.input_height = input_height
        self.input_width = input_width
        self.normalize_mean = normalize_mean
        self.normalize_std = normalize_std
        self.mask_threshold = mask_threshold
        self.is_training = is_training
        self.horizontal_flip_prob = horizontal_flip_prob

        # Validate that all image/annotation files exist on disk at init time
        # This catches missing files early, not mid-training (REQ-P02-S02-008)
        self._validate_file_paths()

    def _validate_file_paths(self) -> None:
        """
        Check that all image and annotation paths exist on disk.

        Fail loudly here (at Dataset creation time) rather than silently
        during training (REQ-P02-S04-008).
        """
        missing_files = []

        for sample in self.samples:
            image_path = Path(sample.get("image_path", ""))
            annotation_path = Path(sample.get("annotation_path", ""))

            if not image_path.exists():
                missing_files.append(f"Image missing: {image_path}")

            if annotation_path and not annotation_path.exists():
                missing_files.append(f"Annotation missing: {annotation_path}")

        if missing_files:
            error_message = "\n".join(missing_files)
            raise FileNotFoundError(
                f"Found {len(missing_files)} missing files in dataset:\n{error_message}\n"
                "Ensure the Phase 01 pipeline has been run and paths are correct."
            )

    def __len__(self) -> int:
        """Return the number of samples in this split."""
        return len(self.samples)

    def __getitem__(self, index: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        """
        Load and preprocess a single sample by index.

        Inputs:
            index: Integer index into self.samples.

        Outputs:
            Tuple of (image_tensor, mask_tensor, sample_id):
                image_tensor: shape (3, H, W), dtype float32, normalized
                mask_tensor:  shape (1, H, W), dtype float32, values {0.0, 1.0}
                sample_id:    string identifier for this sample (for error tracking)
        """
        sample = self.samples[index]
        sample_id = sample.get("source_sample_id", f"sample_{index}")

        # Load image from disk
        image_path = Path(sample["image_path"])
        try:
            image_pil = Image.open(image_path)
        except Exception as load_error:
            raise RuntimeError(
                f"Failed to load image: {image_path}\n"
                f"Error: {load_error}"
            )

        # Load annotation mask from disk
        annotation_path = Path(sample["annotation_path"])
        try:
            mask_pil = Image.open(annotation_path)
        except Exception as load_error:
            raise RuntimeError(
                f"Failed to load mask: {annotation_path}\n"
                f"Error: {load_error}"
            )

        # Apply preprocessing to image (decode, convert, resize, normalize)
        image_tensor = preprocess_image(
            image_pil=image_pil,
            target_height=self.input_height,
            target_width=self.input_width,
            normalize_mean=self.normalize_mean,
            normalize_std=self.normalize_std,
        )

        # Apply preprocessing to mask (convert, resize, binarize)
        mask_tensor = preprocess_mask(
            mask_pil=mask_pil,
            target_height=self.input_height,
            target_width=self.input_width,
            threshold=self.mask_threshold,
        )

        # Apply training augmentations (REQ-P02-S02-004)
        # Augmentations are train-only; val/test preprocessing is deterministic
        # (REQ-P02-S02-005)
        if self.is_training:
            image_tensor, mask_tensor = apply_random_horizontal_flip(
                image_tensor=image_tensor,
                mask_tensor=mask_tensor,
                flip_probability=self.horizontal_flip_prob,
            )

        return image_tensor, mask_tensor, sample_id


# ============================================================
# STEP 5: DataLoader factory function
# ============================================================

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
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """
    Create train, validation, and test DataLoaders from the Phase 01 manifest.

    This is the top-level factory that ties everything together.

    Inputs:
        manifest_path: Path to Phase 01 dataset_manifest.json.
        input_height: Target image and mask height.
        input_width: Target image and mask width.
        normalize_mean: Per-channel normalization mean.
        normalize_std: Per-channel normalization std.
        mask_threshold: Binarization threshold for masks.
        batch_size: Number of samples per batch.
        horizontal_flip_prob: Probability of horizontal flip in training.
        num_workers: Number of DataLoader worker processes (0 = main process).

    Outputs:
        Tuple of (train_loader, val_loader, test_loader).

    DataLoader characteristics:
        train_loader: shuffle=True (different order each epoch), augmentations active
        val_loader:   shuffle=False (deterministic), no augmentations
        test_loader:  shuffle=False (deterministic), no augmentations
    """
    # Load samples for each split from the Phase 01 manifest
    train_samples = load_manifest_samples(manifest_path, split="train")
    val_samples = load_manifest_samples(manifest_path, split="val")
    test_samples = load_manifest_samples(manifest_path, split="test")

    # Create Dataset objects for each split
    train_dataset = WoundSegmentationDataset(
        samples=train_samples,
        input_height=input_height,
        input_width=input_width,
        normalize_mean=normalize_mean,
        normalize_std=normalize_std,
        mask_threshold=mask_threshold,
        is_training=True,
        horizontal_flip_prob=horizontal_flip_prob,
    )

    val_dataset = WoundSegmentationDataset(
        samples=val_samples,
        input_height=input_height,
        input_width=input_width,
        normalize_mean=normalize_mean,
        normalize_std=normalize_std,
        mask_threshold=mask_threshold,
        is_training=False,  # No augmentations for validation
        horizontal_flip_prob=0.0,
    )

    test_dataset = WoundSegmentationDataset(
        samples=test_samples,
        input_height=input_height,
        input_width=input_width,
        normalize_mean=normalize_mean,
        normalize_std=normalize_std,
        mask_threshold=mask_threshold,
        is_training=False,  # No augmentations for test
        horizontal_flip_prob=0.0,
    )

    # Create DataLoaders — wrap datasets so training loop can iterate batches
    train_loader = DataLoader(
        dataset=train_dataset,
        batch_size=batch_size,
        shuffle=True,          # Shuffle training to randomize batch composition
        num_workers=num_workers,
        drop_last=False,       # Keep last incomplete batch (small dataset)
    )

    val_loader = DataLoader(
        dataset=val_dataset,
        batch_size=batch_size,
        shuffle=False,         # Deterministic evaluation order (REQ-P02-S02-005)
        num_workers=num_workers,
        drop_last=False,
    )

    test_loader = DataLoader(
        dataset=test_dataset,
        batch_size=1,          # Batch size 1 for test to keep per-sample results easy
        shuffle=False,
        num_workers=num_workers,
        drop_last=False,
    )

    print(
        f"DataLoaders created:\n"
        f"  train: {len(train_dataset)} samples, batch_size={batch_size}\n"
        f"  val:   {len(val_dataset)} samples, batch_size={batch_size}\n"
        f"  test:  {len(test_dataset)} samples, batch_size=1"
    )

    return train_loader, val_loader, test_loader
