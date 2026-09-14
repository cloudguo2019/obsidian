"""Validate frozen-ledger Stage 9 outputs without running the strategy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
OUTPUT = EXPERIMENT / "stage9_readonly_v1.0_prelock"
RESULT = EXPERIMENT / "stage9_readonly_result_v1.0_prelock.json"
FORMAL_RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
VALIDATION = EXPERIMENT / "stage9_readonly_validation_v1.0_prelock.json"
FORMAL_MANIFEST = EXPERIMENT / "formal_l2_manifest_v1.0_prelock.json"
EXPECTED_FORMAL_MANIFEST_SHA256 = (
    "6f17406e61a46d034fe6a9f1cc031ee0b614aa927756f0b53e7d49ea54f46196"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    if VALIDATION.exists():
        raise FileExistsError("validation artifact already exists")
    if sha256(FORMAL_MANIFEST) != EXPECTED_FORMAL_MANIFEST_SHA256:
        raise AssertionError("Stage 8 formal manifest changed")
    result = load_json(RESULT)
    formal = load_json(FORMAL_RESULT)
    if result["status"] != "PASS_STAGE9_READONLY_ROBUSTNESS_AND_FALSIFICATION_COMPLETE":
        raise AssertionError("unexpected Stage 9 result status")
    if result["historical_pseudo_lock_status"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("historical pseudo-lock was opened")
    if any(result[key] != 0 for key in (
        "strategy_run_count_increment",
        "performance_path_calculation_count_increment",
        "historical_pseudo_lock_open_count_increment",
    )):
        raise AssertionError("Stage 9 incorrectly increased a forbidden counter")

    profile = pd.read_csv(OUTPUT / "profile_robustness.csv")
    expected_profiles = {f"P{index:02d}" for index in range(24)}
    if set(profile["profile_id"]) != expected_profiles or len(profile) != 24:
        raise AssertionError("registered profile table is incomplete")
    completed = profile[profile["status"] == "COMPLETED"]
    if len(completed) != 23 or int((completed["delta_cagr"] >= 0).sum()) != 23:
        raise AssertionError("profile completion or sign summary differs")
    if profile.loc[profile["profile_id"] == "P21", "status"].iloc[0] != "NOT_RUN":
        raise AssertionError("P21 status changed")

    daily = pd.read_parquet(OUTPUT / "market_regime_daily.parquet")
    daily["session_date"] = pd.to_datetime(daily["session_date"])
    if len(daily) != 851 or daily["session_date"].nunique() != 851:
        raise AssertionError("market-state daily table is not one row per trading session")
    if daily["session_date"].max().date().isoformat() != "2025-09-09":
        raise AssertionError("market-state table boundary changed")
    if set(daily["trend_state"]) - {"UP", "DOWN", "SIDEWAYS"}:
        raise AssertionError("unexpected trend-state label")
    if set(daily["vol_state"]) - {"HIGH_VOL", "NORMAL_VOL"}:
        raise AssertionError("unexpected volatility-state label")

    for account_id, formal_key in (
        ("HD-ANCHOR-001", "p00_dynamic"),
        ("HD-BASE-RM-001", "risk_matched_static"),
    ):
        returns = pd.to_numeric(daily[f"daily_return__{account_id}"], errors="coerce").dropna()
        compounded = float((1.0 + returns).prod() - 1.0)
        expected = float(formal["primary_result"][formal_key]["total_return"])
        if abs(compounded - expected) > 1e-12:
            raise AssertionError(f"state partition does not reconcile to total return: {account_id}")

    summary = pd.read_csv(OUTPUT / "market_regime_summary.csv")
    if len(summary) != 40:
        raise AssertionError("market-state summary row count changed")
    if set(summary["account_id"]) != {
        "HD-ANCHOR-001", "HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001"
    }:
        raise AssertionError("market-state account coverage is incomplete")

    anchor = pd.read_csv(OUTPUT / "anchor_repair.csv")
    if len(anchor) != 5 or int((anchor["status"] == "MATURE_63_TRADING_SESSIONS").sum()) != 4:
        raise AssertionError("anchor-repair event counts changed")
    fills = pd.read_csv(OUTPUT / "signal_fill_diagnostics.csv")
    if len(fills) != 9 or int((fills["status"] == "FILLED").sum()) != 9:
        raise AssertionError("P00 fill diagnostic counts changed")

    batches = pd.read_csv(OUTPUT / "trade_batch_attribution.csv")
    if len(batches) != 5:
        raise AssertionError("dynamic batch attribution count changed")
    attribution = result["robustness"]["exclude_largest_dynamic_batch"]
    arithmetic = (
        float(attribution["frozen_terminal_asset_increment_vs_rm_cny"])
        - float(attribution["largest_positive_batch_contribution_cny"])
    )
    if abs(arithmetic - float(attribution["remaining_terminal_asset_increment_after_subtraction_cny"])) > 1e-9:
        raise AssertionError("best-batch subtraction does not reconcile")

    expected_rows = result["output_rows"]
    actual_rows = {
        "profile_robustness": len(profile),
        "market_regime_daily": len(daily),
        "market_regime_summary": len(summary),
        "market_regime_episodes": len(pd.read_csv(OUTPUT / "market_regime_episodes.csv")),
        "dividend_reliability": len(pd.read_csv(OUTPUT / "dividend_reliability.csv")),
        "anchor_repair": len(anchor),
        "signal_fill_diagnostics": len(fills),
        "trade_batch_attribution": len(batches),
    }
    if actual_rows != expected_rows:
        raise AssertionError("Stage 9 result row counts do not match outputs")

    output_hashes = [
        {
            "path": path.resolve().relative_to(REPO_ROOT.resolve()).as_posix(),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(OUTPUT.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    payload = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE9-READONLY-VALIDATION-1.0-PRELOCK",
        "status": "PASS_STAGE9_READONLY_OUTPUT_INTEGRITY",
        "checks_passed": 18,
        "profile_rows": len(profile),
        "market_regime_daily_rows": len(daily),
        "market_regime_summary_rows": len(summary),
        "maximum_authorized_date": daily["session_date"].max().date().isoformat(),
        "p00_state_partition_total_return_reconciled": True,
        "risk_matched_state_partition_total_return_reconciled": True,
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "output_hashes": output_hashes,
        "stage9_result_sha256": sha256(RESULT),
    }
    with VALIDATION.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
