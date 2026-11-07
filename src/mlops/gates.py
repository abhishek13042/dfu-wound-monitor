"""P10-S04 promotion gates (REQ-P10-S04-002).

Each gate reads the evidence reports a registry record names and returns
``{"passed": bool, "detail": str, ...}``.  A missing or unreadable report fails
its gate: a model is never promoted on evidence nobody produced.

- ``parity``: an ONNX model must have a passing parity report for this exact artifact hash.
- ``no_regression``: pooled Dice on every fixed evaluation set may not fall more than ``DICE_TOLERANCE`` below the
  active model's.  An evaluation set the active model was measured on but the candidate was not fails.
- ``benchmark``: median total latency may not exceed the active model's by more than ``LATENCY_SLACK``, nor
  ``LATENCY_CEILING_S`` in any case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.mlops.registry import PROJECT_ROOT

DICE_TOLERANCE = 0.01
LATENCY_SLACK = 1.20
LATENCY_CEILING_S = 15.0


def _load(path: str | None, root: Path) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return json.loads((root / path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pooled_dice(report: dict[str, Any]) -> float:
    if "summary" in report:  # a P06 validation report
        return float(report["summary"]["segmentation_on_accepted"]["pooled_dice"])
    return float(report["pooled_dice"]["onnx"])  # a P07-S06 parity report scores the ONNX model on the same split


def _p50_total(report: dict[str, Any]) -> float:
    return float(report["latency_s"]["total"]["p50"])


def parity_gate(candidate: dict[str, Any], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    if candidate["runtime"] != "onnx":
        return {"passed": True, "detail": "Not an exported model; parity does not apply"}
    path = candidate.get("evidence", {}).get("parity")
    report = _load(path, root)
    if report is None:
        return {"passed": False, "detail": f"No parity report at {path!r}"}
    if report.get("onnx", {}).get("model_sha256") != candidate["sha256"]:
        return {"passed": False, "detail": "The parity report is for a different artifact"}
    return {"passed": bool(report.get("parity_passed")), "detail": f"parity_passed={report.get('parity_passed')}",
            "report": path}


def no_regression_gate(candidate: dict[str, Any], active: dict[str, Any] | None,
                       root: Path = PROJECT_ROOT) -> dict[str, Any]:
    ours = candidate.get("evidence", {}).get("validation", {})
    theirs = (active or {}).get("evidence", {}).get("validation", {})
    if not ours:
        return {"passed": False, "detail": "No fixed evaluation set was run for the candidate"}
    sets, passed = {}, True
    for name in sorted(set(ours) | set(theirs)):
        mine = _load(ours.get(name), root)
        if mine is None:
            sets[name], passed = {"passed": False, "detail": f"No candidate report for {name}"}, False
            continue
        dice = _pooled_dice(mine)
        if name not in theirs:
            sets[name] = {"passed": True, "candidate": dice, "detail": "No active result to compare"}
            continue
        baseline_report = _load(theirs[name], root)
        if baseline_report is None:
            sets[name], passed = {"passed": False, "detail": f"Active report for {name} is missing"}, False
            continue
        baseline = _pooled_dice(baseline_report)
        ok = dice >= baseline - DICE_TOLERANCE
        passed &= ok
        sets[name] = {"passed": ok, "candidate": round(dice, 4), "active": round(baseline, 4),
                      "difference": round(dice - baseline, 4), "tolerance": DICE_TOLERANCE}
    failed = [name for name, row in sets.items() if not row["passed"]]
    return {"passed": passed, "sets": sets,
            "detail": "No regression" if passed else f"Regression or missing evidence on {', '.join(failed)}"}


def benchmark_gate(candidate: dict[str, Any], active: dict[str, Any] | None,
                   root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = candidate.get("evidence", {}).get("benchmark")
    report = _load(path, root)
    if report is None:
        return {"passed": False, "detail": f"No benchmark report at {path!r}"}
    p50 = _p50_total(report)
    limit = LATENCY_CEILING_S
    active_report = _load((active or {}).get("evidence", {}).get("benchmark"), root)
    if active_report is not None:
        limit = min(limit, _p50_total(active_report) * LATENCY_SLACK)
    ok = p50 <= limit
    return {"passed": ok, "p50_total_s": p50, "limit_s": round(limit, 3),
            "detail": f"p50 {p50:.2f} s against a limit of {limit:.2f} s"}


def run_gates(candidate: dict[str, Any], active: dict[str, Any] | None,
              root: Path = PROJECT_ROOT) -> dict[str, dict[str, Any]]:
    # The candidate compared with itself (re-promoting after a rollback) is still checked against its own evidence.
    baseline = None if active is not None and active["model_version"] == candidate["model_version"] else active
    return {"parity": parity_gate(candidate, root),
            "no_regression": no_regression_gate(candidate, baseline, root),
            "benchmark": benchmark_gate(candidate, baseline, root)}
