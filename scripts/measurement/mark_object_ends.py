"""Mark the two end points of the known object in each marker photo and write the validation manifest (P09-S01).

Name each photo ``d<distance_cm>_a<angle_deg>_<object>-<true_mm>mm_<n>.jpg``, for example
``d30_a15_ruler-100mm_01.jpg``. The tool reads the distance, angle and true length from the name, so only the two
end points are marked by hand.

    python scripts/measurement/mark_object_ends.py data/raw/marker_photos

For each photo not yet in ``manifest.json``, a window opens at full resolution. Use the toolbar's zoom (magnifier)
to get close, switch zoom off again, then click the two end points of the measured span. Keys: Enter saves,
R clears the clicks, S skips the photo, Q stops (closing the window also stops). The manifest is written after every
saved photo, so you can stop and resume. Then run:

    python scripts/evaluation/run_marker_validation.py --data data/raw/marker_photos/manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.measurement.marker import MarkerConfig, detect_marker  # noqa: E402

NAME = re.compile(r"^d(?P<distance>\d+(?:\.\d+)?)_a(?P<angle>\d+(?:\.\d+)?)_(?P<object>[a-z0-9]+)-"
                  r"(?P<true_mm>\d+(?:\.\d+)?)mm_\w+$", re.IGNORECASE)
SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def parse_name(path: Path) -> dict[str, Any]:
    """Read distance, angle, object and true length from a photo name; raise ValueError if it does not match."""
    match = NAME.match(path.stem)
    if not match:
        raise ValueError(f"{path.name}: expected a name like d30_a15_ruler-100mm_01.jpg")
    return {"distance_cm": float(match["distance"]), "angle_deg": float(match["angle"]),
            "object_name": match["object"].lower(), "true_mm": float(match["true_mm"])}


def _number(value: float) -> float | int:
    return int(value) if float(value).is_integer() else value


def entry_for(path: Path, root: Path, p1: list[float], p2: list[float]) -> dict[str, Any]:
    meta = parse_name(path)
    return {"path": path.relative_to(root).as_posix(), "distance_cm": _number(meta["distance_cm"]),
            "angle_deg": _number(meta["angle_deg"]),
            "object": {"name": meta["object_name"], "p1": p1, "p2": p2, "true_mm": meta["true_mm"]}}


def load_manifest(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"images": []}


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest["images"].sort(key=lambda e: e["path"])
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def pending_photos(folder: Path, manifest: dict[str, Any]) -> list[Path]:
    done = {e["path"] for e in manifest["images"]}
    photos = sorted(p for p in folder.rglob("*") if p.suffix.lower() in SUFFIXES)
    return [p for p in photos if p.relative_to(folder).as_posix() not in done]


def mark(photo: Path, rgb: np.ndarray, status: str) -> tuple[str, list[list[float]]]:
    """Show the photo and collect two clicks. Returns (action, points) with action save, skip or quit."""
    import matplotlib.pyplot as plt

    state: dict[str, Any] = {"action": "quit", "points": []}
    keymap = {"keymap.save": [], "keymap.quit": [], "keymap.home": ["h", "home"]}
    with plt.rc_context(keymap):
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.imshow(rgb)
        ax.set_title(f"{photo.name}   marker: {status}\nclick 2 ends - Enter save - R reset - S skip - Q quit",
                     fontsize=10)
        ax.set_axis_off()
        drawn: list[Any] = []

        def redraw() -> None:
            for artist in drawn:
                artist.remove()
            drawn.clear()
            pts = state["points"]
            if pts:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                drawn.extend(ax.plot(xs, ys, "r+-", markersize=18, linewidth=1))
            fig.canvas.draw_idle()

        def on_click(event) -> None:
            toolbar = getattr(fig.canvas, "toolbar", None)
            if toolbar is not None and str(getattr(toolbar, "mode", "")):
                return  # zoom or pan is active
            if event.inaxes is ax and event.button == 1 and len(state["points"]) < 2:
                state["points"].append([round(float(event.xdata), 1), round(float(event.ydata), 1)])
                redraw()

        def on_key(event) -> None:
            key = (event.key or "").lower()
            if key == "enter" and len(state["points"]) == 2:
                state["action"] = "save"
                plt.close(fig)
            elif key == "r":
                state["points"].clear()
                redraw()
            elif key == "s":
                state["action"] = "skip"
                plt.close(fig)
            elif key == "q":
                state["action"] = "quit"
                plt.close(fig)

        fig.canvas.mpl_connect("button_press_event", on_click)
        fig.canvas.mpl_connect("key_press_event", on_key)
        plt.show()
    return state["action"], state["points"] if state["action"] == "save" else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="folder of marker photos")
    parser.add_argument("--config", default=None, help="marker config (default configs/measurement/marker_v1.json)")
    args = parser.parse_args(argv)

    folder = args.folder.resolve()
    manifest_path = folder / "manifest.json"
    manifest = load_manifest(manifest_path)
    config = MarkerConfig.load(args.config) if args.config else MarkerConfig.load()

    photos = pending_photos(folder, manifest)
    bad = []
    for photo in photos:
        try:
            parse_name(photo)
        except ValueError as error:
            bad.append(str(error))
    if bad:
        print("Rename these photos first:\n  " + "\n  ".join(bad))
        return 2
    print(f"{len(manifest['images'])} already marked, {len(photos)} to do.")

    for photo in photos:
        rgb = np.asarray(ImageOps.exif_transpose(Image.open(photo)).convert("RGB"))
        status = detect_marker(rgb, config).status
        action, points = mark(photo, rgb, status)
        if action == "quit":
            break
        if action == "skip":
            print(f"skipped {photo.name}")
            continue
        manifest["images"].append(entry_for(photo, folder, points[0], points[1]))
        save_manifest(manifest_path, manifest)
        print(f"saved {photo.name}: {points[0]} -> {points[1]} (marker {status})")

    print(f"manifest: {manifest_path} ({len(manifest['images'])} photos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
