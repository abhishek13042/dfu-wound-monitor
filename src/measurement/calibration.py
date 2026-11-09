"""REQ-P09-S01-002/004: choose the scale for one photo and say why.

A found marker wins over a typed-in scale, because it is measured in the same photo. When both exist and disagree
beyond the tolerance, the result carries a SCALE_CONFLICT warning instead of silently dropping the user's value.
A rejected marker never supplies a scale; it leaves a warning with its reason code.
"""

from __future__ import annotations

from typing import Any

from src.measurement.engine import Calibration
from src.measurement.marker import NOT_FOUND, REASONS, MarkerReading


def resolve_calibration(user: Calibration | None, reading: MarkerReading | None,
                        tolerance_pct: float) -> tuple[Calibration | None, list[dict[str, Any]]]:
    if reading is None or reading.status == NOT_FOUND:
        return user, []
    fallback = "the scale you entered is used" if user else "only pixel measurements are reported"
    if not reading.found:
        return user, [{"code": reading.status, "message": f"{REASONS[reading.status]}; {fallback}"}]
    marker = reading.calibration
    assert marker is not None
    if user is not None:
        difference = abs(user.pixels_per_mm - marker.pixels_per_mm) / marker.pixels_per_mm * 100
        if difference > tolerance_pct:
            return marker, [{"code": "SCALE_CONFLICT",
                             "message": (f"The marker gives {marker.pixels_per_mm:.3f} px/mm and the entered scale "
                                         f"{user.pixels_per_mm:.3f} px/mm, {difference:.1f}% apart; the marker is used")}]
    return marker, []
