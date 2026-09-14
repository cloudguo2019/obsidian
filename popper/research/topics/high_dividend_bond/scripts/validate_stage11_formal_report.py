"""Read-only integrity validation for the frozen Stage 11 formal report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = REPO_ROOT / "research/topics/high_dividend_bond/experiments/HD-ANCHOR-001"
MANIFEST = EXPERIMENT / "stage11_formal_report_manifest_v1.0_prelock.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_items(items: list[dict], label: str) -> int:
    checked = 0
    for item in items:
        relative = item.get("path")
        expected = item.get("sha256")
        if not relative or not expected:
            continue
        path = REPO_ROOT / relative
        if not path.is_file():
            raise AssertionError(f"{label} missing: {relative}")
        actual = sha256(path)
        if actual != expected:
            raise AssertionError(f"{label} hash changed: {relative}")
        checked += 1
    return checked


def prior_manifest_items(payload: dict) -> list[dict]:
    items: list[dict] = []
    for key in ("parent_bindings", "implementation_and_validation", "result_files"):
        value = payload.get(key, [])
        if isinstance(value, list):
            items.extend(value)
    return items


def main() -> int:
    manifest = load_json(MANIFEST)
    assert manifest["status"] == "PASS_FROZEN_STAGE11_FORMAL_REPORT_RETROSPECTIVE_L2_PRELOCK"
    assert manifest["research_decision_carried_forward"] == "修改"
    assert manifest["evidence_ceiling"] == "L2_RETROSPECTIVE"
    counters = manifest["authorization_and_counters"]
    assert counters["formal_backtest_run_count"] == 1
    assert counters["performance_calculation_count"] == 1
    assert counters["exposure_calibration_run_count"] == 1
    assert counters["stage9_readonly_analysis_run_count"] == 1
    assert counters["stage10_readonly_attribution_run_count"] == 1
    assert counters["stage11_formal_report_run_count"] == 1
    assert counters["historical_pseudo_lock_open_count"] == 0
    assert counters["prospective_lock_open_count"] == 0
    assert counters["dry_run"] is True

    stage11_checked = verify_items(
        manifest["parent_bindings"] + manifest["report_files"], "stage11"
    )
    prior_checked = 0
    for binding in manifest["parent_bindings"]:
        if binding.get("role", "").startswith("frozen_stage"):
            prior = load_json(REPO_ROOT / binding["path"])
            prior_checked += verify_items(prior_manifest_items(prior), binding["path"])

    report = EXPERIMENT / "PHASE11_FORMAL_REPORT_2026-09-14.md"
    text = report.read_text(encoding="utf-8")
    required_markers = (
        "研究决策为`修改`",
        "L2_RETROSPECTIVE",
        "NOT_OPENED_NOT_READ",
        "24项登记配置",
        "复现与只读验证",
        "下一唯一门禁",
    )
    for marker in required_markers:
        if marker not in text:
            raise AssertionError(f"formal report marker missing: {marker}")

    result = {
        "status": "PASS_STAGE11_FORMAL_REPORT_INTEGRITY",
        "stage11_hash_bindings_checked": stage11_checked,
        "prior_manifest_members_checked": prior_checked,
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "research_decision_carried_forward": "修改",
        "evidence_ceiling": "L2_RETROSPECTIVE",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
