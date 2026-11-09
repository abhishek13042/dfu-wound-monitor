"""
Exploratory Data Analysis (EDA) & Annotation Visualization Module — DFU-WoundMonitor.

This module computes statistical distributions across images, annotations, quality issues,
and splits, and renders visual overlay grids for masks, boxes, and quality failure cases.

Coding Style: Beginner-Understandable Python
"""

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def compute_dataset_statistics(manifest_records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute aggregate statistical summaries across dataset samples.

    Inputs:
        manifest_records: List of sample manifest dictionaries.

    Outputs:
        Dictionary containing image dimension stats, aspect ratios, mask areas,
        and split distributions.

    Assumptions:
        Input list contains valid canonical sample records.
    """
    total_samples = len(manifest_records)
    if total_samples == 0:
        return {"error": "No manifest records provided"}

    widths: list[int] = []
    heights: list[int] = []
    aspect_ratios: list[float] = []
    wound_area_ratios: list[float] = []

    split_counts: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    canonical_label_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}

    for sample in manifest_records:
        w = sample.get("width", 0)
        h = sample.get("height", 0)

        if w > 0 and h > 0:
            widths.append(w)
            heights.append(h)
            aspect_ratios.append(round(w / h, 4))

        # Track split count
        split = sample.get("split", "unassigned")
        split_counts[split] = split_counts.get(split, 0) + 1

        # Track canonical label count
        label = sample.get("canonical_label", "unknown")
        canonical_label_counts[label] = canonical_label_counts.get(label, 0) + 1

        # Track issue count if invalid
        issue = sample.get("issue_category")
        if issue:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        # Track mask area ratio if available
        mask_stats = sample.get("mask_metadata")
        if mask_stats and "wound_area_ratio" in mask_stats:
            wound_area_ratios.append(mask_stats["wound_area_ratio"])

    # Compute descriptive statistics
    def get_stats(data_list: list[int] | list[float]) -> dict[str, float]:
        if not data_list:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}
        arr = np.array(data_list)
        return {
            "mean": float(np.round(np.mean(arr), 4)),
            "min": float(np.round(np.min(arr), 4)),
            "max": float(np.round(np.max(arr), 4)),
            "median": float(np.round(np.median(arr), 4))
        }

    return {
        "total_samples": total_samples,
        "split_counts": split_counts,
        "canonical_label_counts": canonical_label_counts,
        "issue_counts": issue_counts,
        "width_stats": get_stats(widths),
        "height_stats": get_stats(heights),
        "aspect_ratio_stats": get_stats(aspect_ratios),
        "wound_area_ratio_stats": get_stats(wound_area_ratios) if wound_area_ratios else None
    }


def draw_segmentation_overlay(
    image: Image.Image,
    mask_array: np.ndarray,
    color: tuple[int, int, int] = (255, 0, 0),
    alpha: float = 0.4
) -> Image.Image:
    """
    Render a semi-transparent color overlay of a binary segmentation mask onto an RGB image.

    Inputs:
        image: PIL Image object (RGB format, H x W x C).
        mask_array: 2D NumPy array (H x W) where >0 indicates wound tissue.
        color: RGB tuple for overlay color (default Red: 255, 0, 0).
        alpha: Transparency ratio between 0.0 and 1.0 (default 0.4).

    Outputs:
        Blended PIL Image object with mask overlay.
    """
    # Convert image to RGBA for alpha blending
    img_rgba = image.convert("RGBA")

    # Create solid color overlay image
    width, height = img_rgba.size
    overlay_data = np.zeros((height, width, 4), dtype=np.uint8)

    # Set RGB color where mask > 0
    mask_boolean = (mask_array > 0)
    overlay_data[mask_boolean, 0] = color[0]
    overlay_data[mask_boolean, 1] = color[1]
    overlay_data[mask_boolean, 2] = color[2]
    overlay_data[mask_boolean, 3] = int(255 * alpha)  # Alpha opacity channel

    overlay_img = Image.fromarray(overlay_data, mode="RGBA")

    # Composite overlay over original image
    blended_img = Image.alpha_composite(img_rgba, overlay_img)
    return blended_img.convert("RGB")


def create_visualization_grid(
    image_paths: list[Path],
    mask_paths: list[Path | None],
    labels: list[str],
    output_grid_path: Path,
    cols: int = 4
) -> Path:
    """
    Generate a grid panel image of samples with overlays and text captions.

    Inputs:
        image_paths: List of sample image file paths.
        mask_paths: List of corresponding mask file paths (or None).
        labels: List of text labels to draw above/below each panel.
        output_grid_path: Destination path for saved grid PNG.
        cols: Number of columns in grid layout (default 4).

    Outputs:
        Path object pointing to saved visualization grid file.
    """
    num_samples = len(image_paths)
    if num_samples == 0:
        print("Warning: No samples provided for visualization grid.")
        return output_grid_path

    # Standard cell dimension for grid thumbnails
    cell_w, cell_h = 300, 300
    rows = (num_samples + cols - 1) // cols

    grid_w = cols * cell_w
    grid_h = rows * cell_h

    # Create blank white background image
    grid_image = Image.new("RGB", (grid_w, grid_h), color=(240, 240, 240))
    draw = ImageDraw.Draw(grid_image)

    for i in range(num_samples):
        img_path = image_paths[i]
        mask_path = mask_paths[i] if i < len(mask_paths) else None
        caption = labels[i] if i < len(labels) else f"Sample {i+1}"

        r = i // cols
        c = i % cols
        x_offset = c * cell_w
        y_offset = r * cell_h

        try:
            with Image.open(img_path) as orig_img:
                orig_rgb = orig_img.convert("RGB")

                # Apply mask overlay if present
                if mask_path is not None and mask_path.exists():
                    with Image.open(mask_path) as mask_img:
                        mask_arr = np.array(mask_img)
                        rendered_cell = draw_segmentation_overlay(orig_rgb, mask_arr)
                else:
                    rendered_cell = orig_rgb

                # Resize to cell thumbnail size
                thumbnail = rendered_cell.resize((cell_w, cell_h - 30), Image.Resampling.LANCZOS)
                grid_image.paste(thumbnail, (x_offset, y_offset + 30))

                # Draw caption header
                draw.rectangle([x_offset, y_offset, x_offset + cell_w, y_offset + 30], fill=(40, 40, 40))
                draw.text((x_offset + 10, y_offset + 5), caption[:35], fill=(255, 255, 255))

        except Exception:
            draw.rectangle([x_offset, y_offset, x_offset + cell_w, y_offset + cell_h], fill=(200, 100, 100))
            draw.text((x_offset + 10, y_offset + 10), f"Error loading\n{img_path.name}", fill=(255, 255, 255))

    # Ensure parent output directory exists
    os.makedirs(output_grid_path.parent, exist_ok=True)
    grid_image.save(output_grid_path)
    print(f"Saved visualization grid artifact to: {output_grid_path}")
    return output_grid_path
