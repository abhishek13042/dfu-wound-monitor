"""P10-S01: the alert rules use only real dfu_ metrics, and every alert has a promtool test.

The rules themselves are evaluated by `promtool test rules` in the `observability` CI job.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.observability import metrics
from src.observability.errors import init_error_reporting, scrub_event

yaml = pytest.importorskip("yaml")
ROOT = Path(__file__).resolve().parents[2] / "docker" / "production" / "observability"
REQUIRED = {"DfuHighErrorRate", "DfuQueueBacklog", "DfuModelNotReady"}


def _known_series() -> set[str]:
    names = set()
    for collector in metrics.REGISTRY.collect():
        names.add(collector.name)
        names.update(f"{collector.name}{suffix}" for suffix in ("_total", "_bucket", "_count", "_sum"))
    return names


def _rules() -> list[dict]:
    return [rule for group in yaml.safe_load((ROOT / "alerts.yml").read_text())["groups"] for rule in group["rules"]]


def test_required_alerts_exist_and_use_known_metrics():
    rules = _rules()
    assert REQUIRED <= {rule["alert"] for rule in rules}
    known = _known_series()
    for rule in rules:
        used = set(re.findall(r"\bdfu_[a-z_]+", rule["expr"]))
        assert used and used <= known, (rule["alert"], used - known)
        assert rule["for"] and rule["labels"]["severity"] in {"page", "ticket"}
        assert rule["annotations"]["runbook"].startswith("docs/runbooks/observability.md#")


def test_every_alert_has_a_firing_promtool_case():
    tests = yaml.safe_load((ROOT / "alerts_test.yml").read_text())["tests"]
    firing = {case["alertname"] for test in tests for case in test["alert_rule_test"] if case["exp_alerts"]}
    assert {rule["alert"] for rule in _rules()} <= firing


def test_runbook_has_a_section_per_alert():
    runbook = (ROOT.parents[2] / "docs" / "runbooks" / "observability.md").read_text().lower()
    for rule in _rules():
        anchor = rule["annotations"]["runbook"].split("#")[1]
        assert f"## {anchor.replace('-', ' ')}" in runbook


def test_dashboard_queries_known_metrics():
    dashboard = json.loads((ROOT / "grafana-dashboard.json").read_text())
    known = _known_series()
    for panel in dashboard["panels"]:
        assert set(re.findall(r"\bdfu_[a-z_]+", panel["targets"][0]["expr"])) <= known


def test_error_reporting_is_off_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_error_reporting("test") is False


def test_error_events_are_scrubbed_before_sending():
    event = {"request": {"headers": {"Authorization": "Bearer abc.def"}},
             "exception": {"values": [{"value": 'open filename="Mr Jones heel.jpg" with Bearer abc.def'}]}}
    cleaned = json.dumps(scrub_event(event))
    assert "Mr Jones" not in cleaned and "abc.def" not in cleaned and "request" not in scrub_event(event)
