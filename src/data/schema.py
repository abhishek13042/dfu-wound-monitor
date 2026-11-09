"""
Dataset Schema and Label Harmonization Module — DFU-WoundMonitor.

This module defines the canonical metadata schema representation and explicit label mapping dictionary.
Key Rule: Standardize representation, NOT meaning. Original source labels are always preserved.

Coding Style: Beginner-Understandable Python
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CanonicalSampleMetadata:
    """
    Canonical metadata representation for a single dataset sample.

    Missing fields remain None / UNKNOWN per project governance rules.
    """
    dataset_name: str
    dataset_version: str
    source_sample_id: str
    image_path: str
    annotation_path: str | None
    checksum_sha256: str
    width: int
    height: int
    channels: int
    annotation_type: str  # 'detection', 'wound_segmentation', 'tissue_segmentation', 'classification'
    patient_id: str | None  # None if unavailable
    exam_id: str | None     # None if unavailable
    original_label: str
    canonical_label: str
    metadata_status: str       # 'VERIFIED', 'INFERRED', 'UNKNOWN'
    validation_status: str     # 'VALID', 'INVALID', 'QUARANTINED'
    annotation_checksum_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert dataclass instance to standard dictionary."""
        return asdict(self)


# Explicit Source -> Canonical Label Mapping Registry
LABEL_MAPPING_REGISTRY: dict[str, dict[str, dict[str, str]]] = {
    "DFUC2020": {
        "wound": {
            "canonical_label": "wound",
            "mapping_status": "VERIFIED",
            "task_type": "detection",
            "notes": "Bounding box localization target for ulcer region."
        }
    },
    "DFUC2021": {
        "Infection": {
            "canonical_label": "pathology_infection",
            "mapping_status": "VERIFIED",
            "task_type": "classification",
            "notes": "Clinical classification flag for infection presence."
        },
        "Ischemia": {
            "canonical_label": "pathology_ischemia",
            "mapping_status": "VERIFIED",
            "task_type": "classification",
            "notes": "Clinical classification flag for ischemia presence."
        },
        "Both": {
            "canonical_label": "pathology_both",
            "mapping_status": "VERIFIED",
            "task_type": "classification",
            "notes": "Clinical classification flag for combined infection and ischemia."
        },
        "None": {
            "canonical_label": "pathology_none",
            "mapping_status": "VERIFIED",
            "task_type": "classification",
            "notes": "Clinical classification flag for control/neither pathology."
        }
    },
    "DFUC2022": {
        "wound": {
            "canonical_label": "wound_tissue",
            "mapping_status": "VERIFIED",
            "task_type": "wound_segmentation",
            "notes": "Binary semantic segmentation foreground mask target."
        },
        "background": {
            "canonical_label": "background",
            "mapping_status": "VERIFIED",
            "task_type": "wound_segmentation",
            "notes": "Binary semantic segmentation background target."
        }
    },
    "DFUTissueSegNet": {
        # Classes per the source palette (DFUTissue/Labeled/*/Palette/palette_colorCode.txt):
        # Red=Fibrin, Green=Granulation, Blue=Callus.  Slough/eschar are not
        # labeled classes in the released masks.
        "granulation": {
            "canonical_label": "tissue_granulation",
            "mapping_status": "VERIFIED",
            "task_type": "tissue_segmentation",
            "notes": "Palette green. Pink/red granulation tissue."
        },
        "fibrin": {
            "canonical_label": "tissue_fibrin",
            "mapping_status": "VERIFIED",
            "task_type": "tissue_segmentation",
            "notes": "Palette red. Yellow/white fibrinous (slough-like) tissue."
        },
        "callus": {
            "canonical_label": "tissue_callus",
            "mapping_status": "VERIFIED",
            "task_type": "tissue_segmentation",
            "notes": "Palette blue. Hyperkeratotic callus around the ulcer."
        },
        "background": {
            "canonical_label": "background",
            "mapping_status": "VERIFIED",
            "task_type": "tissue_segmentation",
            "notes": "Palette black. Background skin/surroundings."
        }
    },
    "FUSeg2021": {
        "wound": {
            "canonical_label": "wound_tissue",
            "mapping_status": "VERIFIED",
            "task_type": "wound_segmentation",
            "notes": "Primary SPEC-02-01 binary wound segmentation mask target."
        },
        "background": {
            "canonical_label": "background",
            "mapping_status": "VERIFIED",
            "task_type": "wound_segmentation",
            "notes": "Primary SPEC-02-01 binary wound segmentation background target."
        }
    }
}


def map_source_label_to_canonical(
    dataset_name: str,
    original_label: str
) -> tuple[str, str, str]:
    """
    Look up canonical label mapping for a source dataset and label.

    Inputs:
        dataset_name: Name of dataset (e.g. 'DFUC2022').
        original_label: Source label string.

    Outputs:
        Tuple of (canonical_label, mapping_status, notes).
    """
    dataset_registry = LABEL_MAPPING_REGISTRY.get(dataset_name, {})
    mapping_info = dataset_registry.get(original_label)

    if mapping_info is not None:
        return (
            mapping_info["canonical_label"],
            mapping_info["mapping_status"],
            mapping_info["notes"]
        )

    # Fallback if label is unmapped or custom
    return (original_label, "UNMAPPED", "No explicit mapping defined in registry.")


def create_canonical_sample_metadata(
    dataset_name: str,
    dataset_version: str,
    source_sample_id: str,
    image_path: str,
    annotation_path: str | None,
    checksum_sha256: str,
    width: int,
    height: int,
    channels: int,
    annotation_type: str,
    patient_id: str | None,
    exam_id: str | None,
    original_label: str,
    validation_status: str,
    annotation_checksum_sha256: str | None = None,
) -> CanonicalSampleMetadata:
    """
    Construct a validated CanonicalSampleMetadata instance.

    Inputs:
        All required fields for CanonicalSampleMetadata dataclass.

    Outputs:
        Instantiated CanonicalSampleMetadata object.
    """
    canonical_label, mapping_status, _ = map_source_label_to_canonical(
        dataset_name, original_label
    )

    metadata_status = "VERIFIED" if (patient_id is not None or mapping_status == "VERIFIED") else "INFERRED"

    return CanonicalSampleMetadata(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        source_sample_id=source_sample_id,
        image_path=image_path,
        annotation_path=annotation_path,
        checksum_sha256=checksum_sha256,
        width=width,
        height=height,
        channels=channels,
        annotation_type=annotation_type,
        patient_id=patient_id,
        exam_id=exam_id,
        original_label=original_label,
        canonical_label=canonical_label,
        metadata_status=metadata_status,
        validation_status=validation_status,
        annotation_checksum_sha256=annotation_checksum_sha256,
    )
