"""P10-S04: the registry refuses incomplete records, gates block a regression, rollback is one step,
and drift is reported as a change in inputs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from scripts.deployment import promote_model
from src.mlops import drift
from src.mlops.gates import run_gates
from src.mlops.registry import REQUIRED, Registry, RegistryError, file_sha256


def _validation(dice: float) -> dict:
    return {"summary": {"segmentation_on_accepted": {"pooled_dice": dice}}}


def _benchmark(p50: float) -> dict:
    return {"latency_s": {"total": {"p50": p50}}}


@pytest.fixture
def world(tmp_path):
    """Two model artifacts with their evidence reports, under ``tmp_path``."""

    def write(name: str, payload) -> str:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload) if isinstance(payload, bytes) else path.write_text(json.dumps(payload))
        return name

    def record(version: str, dice: float, external: float | None, p50: float, weights: bytes) -> dict:
        artifact = write(f"models/{version}.pth", weights)
        validation = {"fuseg2021_test": write(f"reports/{version}_fuseg.json", _validation(dice))}
        if external is not None:
            validation["lowerlimb_external"] = write(f"reports/{version}_ext.json", _validation(external))
        return {"model_version": version, "sha256": file_sha256(tmp_path / artifact), "runtime": "pytorch",
                "artifact_path": artifact, "inference_config": f"configs/{version}.json",
                "dataset_refs": [{"dataset": "FUSeg2021", "version": "v1"}], "metrics": {"pooled_dice": dice},
                "limitations": ["Foot ulcers only."], "status": "CANDIDATE", "approved_by": None,
                "evidence": {"validation": validation,
                             "benchmark": write(f"reports/{version}_bench.json", _benchmark(p50))}}

    return tmp_path, record, write


@pytest.mark.parametrize("field", REQUIRED)
def test_registry_requires_fields(tmp_path, world, field):
    _, record, _ = world
    entry = record("m1", 0.92, 0.25, 3.0, b"one")
    del entry[field]
    registry = Registry(tmp_path / "registry.json")
    if field in ("status", "approved_by"):  # register sets these itself; a stored record without them is refused
        registry.register(entry)
        broken = registry.get("m1")
        del broken[field]
        registry.save()
        with pytest.raises(RegistryError, match=field):
            Registry(tmp_path / "registry.json")
    else:
        with pytest.raises(RegistryError):
            registry.register(entry)


def test_registry_refuses_empty_limitations_and_reused_versions(tmp_path, world):
    _, record, _ = world
    registry = Registry(tmp_path / "registry.json")
    with pytest.raises(RegistryError, match="limitations"):
        registry.register({**record("m1", 0.92, 0.25, 3.0, b"one"), "limitations": []})
    registry.register(record("m1", 0.92, 0.25, 3.0, b"one"))
    with pytest.raises(RegistryError, match="never reused"):
        registry.register(record("m1", 0.93, 0.26, 3.0, b"one"))


def _active(root, record) -> Registry:
    registry = Registry(root / "registry.json", root)
    registry.register(record("old", 0.92, 0.25, 3.0, b"old weights"))
    registry.promote("old", "Reviewer A", run_gates(registry.get("old"), None, root))
    return registry


def test_gate_blocks_regression(world):
    root, record, _ = world
    registry = _active(root, record)
    registry.register(record("worse", 0.88, 0.25, 3.0, b"worse weights"))  # 0.04 below on the held-out set
    gates = run_gates(registry.get("worse"), registry.active(), root)

    assert not gates["no_regression"]["passed"]
    assert gates["no_regression"]["sets"]["fuseg2021_test"]["difference"] == pytest.approx(-0.04)
    with pytest.raises(RegistryError, match="gate"):
        registry.promote("worse", "Reviewer A", gates)
    assert registry.active()["model_version"] == "old"


def test_gate_blocks_missing_evidence_and_slow_models(world):
    root, record, _ = world
    registry = _active(root, record)
    registry.register(record("partial", 0.93, None, 3.0, b"partial"))  # never run on the external set
    registry.register(record("slow", 0.93, 0.26, 9.0, b"slow"))       # 3x the active model's latency
    partial = run_gates(registry.get("partial"), registry.active(), root)
    slow = run_gates(registry.get("slow"), registry.active(), root)

    assert not partial["no_regression"]["passed"] and "lowerlimb_external" in partial["no_regression"]["detail"]
    assert not slow["benchmark"]["passed"]


def test_promotion_needs_a_named_person(world):
    root, record, _ = world
    registry = _active(root, record)
    registry.register(record("better", 0.93, 0.27, 2.5, b"better"))
    gates = run_gates(registry.get("better"), registry.active(), root)
    assert all(gate["passed"] for gate in gates.values())
    with pytest.raises(RegistryError, match="approver"):
        registry.promote("better", "  ", gates)


def test_rollback_drill(world, capsys):
    """Promote through the command line, then roll back with one command; the old artifact is hash-checked."""

    root, record, _ = world
    registry = _active(root, record)
    registry.register(record("new", 0.93, 0.27, 2.5, b"new weights"))
    registry.save()
    base = ["--registry", str(root / "registry.json"), "--root", str(root)]

    assert promote_model.main([*base, "promote", "new", "--approved-by", "Reviewer B"]) == 0
    assert Registry(root / "registry.json").active()["model_version"] == "new"

    assert promote_model.main([*base, "rollback", "--approved-by", "On-call C"]) == 0
    after = Registry(root / "registry.json")
    assert after.active()["model_version"] == "old"
    assert after.get("new")["status"] == "RETIRED"
    assert [event["action"] for event in after.data["events"]][-2:] == ["PROMOTE_ACTIVE", "ROLLBACK"]

    capsys.readouterr()
    assert promote_model.main([*base, "active-config"]) == 0
    assert capsys.readouterr().out.strip() == "configs/old.json"


def test_a_tampered_artifact_is_refused(world):
    root, record, write = world
    registry = _active(root, record)
    write("models/old.pth", b"swapped weights")
    with pytest.raises(RegistryError, match="hash"):
        registry.verify_artifact(registry.active())


def _rows(rng, n, luminance=120.0, blur=300.0, rejected=0.0):
    rows = []
    for index in range(n):
        status = "QUALITY_REJECTED" if index < int(n * rejected) else "COMPLETED"
        rows.append({"status": status, "mean_luminance": float(rng.normal(luminance, 15)),
                     "laplacian_variance": float(rng.lognormal(np.log(blur), 0.4)),
                     "megapixels": 0.262144, "predicted_area_share": float(rng.uniform(0.005, 0.05))})
    return rows


def test_drift_detects_shift():
    rng = np.random.default_rng(7)
    reference = drift.build_reference(_rows(rng, 400), source="synthetic")
    same = drift.check(reference, _rows(rng, 200))
    darker = drift.check(reference, _rows(rng, 200, luminance=70.0, blur=80.0, rejected=0.3))

    assert same["status"] == "STABLE", same["features"]
    assert darker["status"] == "DRIFT"
    assert {"mean_luminance", "laplacian_variance", "quality_rejection_rate"} <= set(darker["alert"]["features"])
    assert "not a measured change in accuracy" in darker["alert"]["message"]
    assert "accuracy" not in json.dumps({k: v for k, v in darker.items() if k != "alert"})


def test_drift_needs_enough_data_and_a_fresh_reference():
    rng = np.random.default_rng(8)
    reference = drift.build_reference(_rows(rng, 400), source="synthetic")
    few = drift.check(reference, _rows(rng, 10))
    later = drift.check(reference, _rows(rng, 200), now=datetime.now(UTC) + timedelta(days=200))

    assert few["status"] == "INSUFFICIENT_DATA"
    assert any("older than" in note for note in later["notes"])


def test_features_come_from_a_stored_record():
    record = {"status": "COMPLETED",
              "quality": {"measurements": {"mean_luminance": 101.5, "laplacian_variance": 250.0}},
              "provenance": {"input": {"width": 1000, "height": 500}},
              "measurement": {"pixel": {"area_px": 2000}, "provenance": {"measurement": {"mask_shape": [500, 1000]}}}}
    row = drift.features_from_record(record)
    assert row == {"status": "COMPLETED", "mean_luminance": 101.5, "laplacian_variance": 250.0,
                   "megapixels": 0.5, "predicted_area_share": 0.004}


def test_check_drift_reads_the_analyses_table(tmp_path, capsys):
    from sqlalchemy import insert

    from scripts.monitoring import check_drift
    from src.storage.database import create_database_engine
    from src.storage.models import Analysis, Base

    rng = np.random.default_rng(9)
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(json.dumps(drift.build_reference(_rows(rng, 400), source="synthetic")))
    url = f"sqlite:///{(tmp_path / 'drift.sqlite3').as_posix()}"
    engine = create_database_engine(url, foreign_keys=False)
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        for index, row in enumerate(_rows(rng, 80, luminance=60.0)):
            record = {"status": row["status"], "quality": {"measurements": {
                "mean_luminance": row["mean_luminance"], "laplacian_variance": row["laplacian_variance"]}},
                "provenance": {"input": {"width": 512, "height": 512}}}
            created = now - timedelta(days=30 if index < 10 else 1)  # ten are outside the window
            connection.execute(insert(Analysis).values(
                analysis_id=f"ana_{index:04d}", owner_id="usr_drift", image_id=f"img_{index:04d}", status=row["status"],
                model_version="m1", created_at=created.isoformat(), record_json=json.dumps(record)))
    engine.dispose()

    code = check_drift.main(["--database-url", url, "--days", "7", "--reference", str(reference_path),
                             "--output", str(tmp_path / "drift.json")])
    report = json.loads((tmp_path / "drift.json").read_text())
    capsys.readouterr()

    assert code == 1 and report["status"] == "DRIFT" and report["samples"] == 70
    assert report["features"]["mean_luminance"]["status"] == "SHIFT"
    assert report["features"]["predicted_area_share"]["status"] == "INSUFFICIENT_DATA"
