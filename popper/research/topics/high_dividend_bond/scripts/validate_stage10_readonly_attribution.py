"""Independently validate Stage 10 frozen-ledger attribution outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
OUTPUT = EXPERIMENT / "stage10_readonly_v1.0_prelock"
RESULT = EXPERIMENT / "stage10_readonly_result_v1.0_prelock.json"
VALIDATION = EXPERIMENT / "stage10_readonly_validation_v1.0_prelock.json"
FORMAL_MANIFEST = EXPERIMENT / "formal_l2_manifest_v1.0_prelock.json"
STAGE9_MANIFEST = EXPERIMENT / "stage9_readonly_manifest_v1.0_prelock.json"
FORMAL_RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
TOLERANCE = 0.01
EXPECTED_FORMAL_MANIFEST_SHA256 = "6f17406e61a46d034fe6a9f1cc031ee0b614aa927756f0b53e7d49ea54f46196"
EXPECTED_STAGE9_MANIFEST_SHA256 = "1eb1a6e979825ff62e38017bf2b105ac09853b7ad70d61e649da45fb4b7b41f7"
COMPONENTS = (
    "price_pnl_cny",
    "execution_price_pnl_cny",
    "gross_dividend_entitlement_cny",
    "tax_effect_cny",
    "fee_effect_cny",
    "cash_yield_cny",
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


def assert_close(left: float, right: float, label: str) -> None:
    if abs(float(left) - float(right)) > TOLERANCE:
        raise AssertionError(f"{label}: {left} != {right}")


def main() -> None:
    if VALIDATION.exists():
        raise FileExistsError("Stage 10 validation artifact already exists")
    if sha256(FORMAL_MANIFEST) != EXPECTED_FORMAL_MANIFEST_SHA256:
        raise AssertionError("Stage 8 formal manifest changed")
    if sha256(STAGE9_MANIFEST) != EXPECTED_STAGE9_MANIFEST_SHA256:
        raise AssertionError("Stage 9 manifest changed")

    result = load_json(RESULT)
    formal = load_json(FORMAL_RESULT)
    if result["status"] != "PASS_STAGE10_FULL_RETURN_ATTRIBUTION_FROM_FROZEN_LEDGER":
        raise AssertionError("unexpected Stage 10 result status")
    if result["historical_pseudo_lock_status"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("historical pseudo-lock was opened")
    if any(result[key] != 0 for key in (
        "strategy_run_count_increment",
        "performance_path_calculation_count_increment",
        "historical_pseudo_lock_open_count_increment",
    )):
        raise AssertionError("Stage 10 incorrectly increased a forbidden counter")

    daily = pd.read_parquet(OUTPUT / "daily_attribution.parquet")
    accounts = pd.read_csv(OUTPUT / "account_component_summary.csv")
    relative = pd.read_csv(OUTPUT / "relative_component_summary.csv")
    annual = pd.read_csv(OUTPUT / "annual_relative_attribution.csv")
    segments = pd.read_csv(OUTPUT / "inventory_opportunity_segments.csv")
    batches = pd.read_csv(OUTPUT / "dynamic_batch_attribution.csv")
    fees = pd.read_csv(OUTPUT / "fee_breakdown.csv")

    expected_accounts = {
        "HD-ANCHOR-001", "HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001"
    }
    expected_baselines = {"HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001"}
    if len(accounts) != 4 or set(accounts["account_id"]) != expected_accounts:
        raise AssertionError("account component summary coverage changed")
    if len(relative) != 3 or set(relative["baseline_account_id"]) != expected_baselines:
        raise AssertionError("relative component summary coverage changed")
    if len(daily) != 2556 or set(daily["baseline_account_id"]) != expected_baselines:
        raise AssertionError("daily relative attribution coverage changed")
    dates = pd.to_datetime(daily["session_date"])
    if dates.min().date().isoformat() != "2022-03-10" or dates.max().date().isoformat() != "2025-09-09":
        raise AssertionError("Stage 10 daily date boundary changed")
    if dates.nunique() != 852:
        raise AssertionError("Stage 10 daily session count changed")

    for _, row in accounts.iterrows():
        attributed = sum(float(row[item]) for item in COMPONENTS)
        assert_close(attributed, row["attributed_nav_gain_cny"], "absolute component sum")
        assert_close(
            float(row["final_nav_cny"]) - float(row["initial_nav_cny"]),
            row["attributed_nav_gain_cny"],
            "absolute NAV identity",
        )
        if abs(float(row["period_identity_difference_cny"])) > TOLERANCE:
            raise AssertionError("account period identity exceeds tolerance")
        if abs(float(row["maximum_absolute_daily_reconciliation_cny"])) > TOLERANCE:
            raise AssertionError("source daily reconciliation exceeds tolerance")

    relative_component_columns = [f"relative_{item}" for item in COMPONENTS]
    daily_attributed = daily[relative_component_columns].sum(axis=1)
    if (daily_attributed - daily["relative_attributed_nav_change_cny"]).abs().max() > TOLERANCE:
        raise AssertionError("daily relative component sum failed")
    if (
        daily["relative_actual_nav_change_cny"]
        - daily["relative_attributed_nav_change_cny"]
    ).abs().max() > TOLERANCE:
        raise AssertionError("daily relative identity failed")
    if daily["relative_cash_yield_cny"].abs().max() != 0:
        raise AssertionError("P00 cash yield is not zero")

    for _, row in relative.iterrows():
        attributed = sum(float(row[f"relative_{item}"]) for item in COMPONENTS)
        assert_close(attributed, row["relative_attributed_nav_change_cny"], "relative component sum")
        assert_close(
            row["terminal_nav_difference_cny"],
            row["relative_attributed_nav_change_cny"],
            "relative terminal identity",
        )
        if abs(float(row["relative_period_identity_difference_cny"])) > TOLERANCE:
            raise AssertionError("relative period identity exceeds tolerance")

    strategy_final = float(
        accounts.loc[accounts["account_id"] == "HD-ANCHOR-001", "final_nav_cny"].iloc[0]
    )
    risk_final = float(
        accounts.loc[accounts["account_id"] == "HD-BASE-RM-001", "final_nav_cny"].iloc[0]
    )
    assert_close(strategy_final, formal["primary_result"]["p00_dynamic"]["final_nav_cny"], "P00 final NAV")
    assert_close(risk_final, formal["primary_result"]["risk_matched_static"]["final_nav_cny"], "RM final NAV")
    assert_close(
        strategy_final - risk_final,
        formal["primary_result"]["p00_vs_risk_matched"]["terminal_asset_difference_cny"],
        "primary terminal difference",
    )

    for frame, identity_column, label in (
        (annual, "relative_identity_difference_cny", "annual"),
        (segments, "relative_identity_difference_cny", "segment"),
    ):
        if frame[identity_column].abs().max() > TOLERANCE:
            raise AssertionError(f"{label} identity exceeds tolerance")
        for baseline_id in expected_baselines:
            total = frame.loc[
                frame["baseline_account_id"] == baseline_id,
                "relative_actual_nav_change_cny",
            ].sum()
            expected = relative.loc[
                relative["baseline_account_id"] == baseline_id,
                "terminal_nav_difference_cny",
            ].iloc[0]
            assert_close(total, expected, f"{label} partition for {baseline_id}")

    if len(annual) != 12 or set(annual["calendar_year"]) != {2022, 2023, 2024, 2025}:
        raise AssertionError("annual attribution coverage changed")
    if len(batches) != 5:
        raise AssertionError("dynamic batch count changed")
    if int((batches["status"] == "CLOSED_LOGICAL_DYNAMIC_BATCH").sum()) != 4:
        raise AssertionError("closed dynamic batch count changed")
    if int((batches["status"] == "OPEN_MARKED_AT_TERMINAL").sum()) != 1:
        raise AssertionError("terminal open batch count changed")
    if batches["batch_identity_difference_cny"].abs().max() > TOLERANCE:
        raise AssertionError("dynamic batch identity exceeds tolerance")
    overlay = float(
        relative.loc[
            relative["baseline_account_id"] == "HD-BASE-000",
            "terminal_nav_difference_cny",
        ].iloc[0]
    )
    assert_close(batches["net_contribution_cny"].sum(), overlay, "dynamic overlay batch identity")

    total_fee = float(fees.loc[fees["item"] == "TOTAL_TRANSACTION_FEES", "amount_cny"].iloc[0])
    fee_subtotal = float(
        fees.loc[fees["classification"] == "TRANSACTION_FEE_SUBCOMPONENT", "amount_cny"].sum()
    )
    assert_close(total_fee, fee_subtotal, "fee detail identity")
    p00_fee_effect = float(
        accounts.loc[accounts["account_id"] == "HD-ANCHOR-001", "fee_effect_cny"].iloc[0]
    )
    assert_close(total_fee, -p00_fee_effect, "fee NAV attribution identity")

    expected_rows = result["output_rows"]
    actual_rows = {
        "daily_attribution": len(daily),
        "account_component_summary": len(accounts),
        "relative_component_summary": len(relative),
        "annual_relative_attribution": len(annual),
        "inventory_opportunity_segments": len(segments),
        "dynamic_batch_attribution": len(batches),
        "fee_breakdown": len(fees),
    }
    if expected_rows != actual_rows:
        raise AssertionError("Stage 10 result row counts do not match outputs")

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
        "artifact_version": "HD-STAGE10-READONLY-VALIDATION-1.0-PRELOCK",
        "status": "PASS_STAGE10_READONLY_ATTRIBUTION_OUTPUT_INTEGRITY",
        "checks_passed": 24,
        "daily_attribution_rows": len(daily),
        "account_summary_rows": len(accounts),
        "relative_summary_rows": len(relative),
        "annual_rows": len(annual),
        "inventory_segment_rows": len(segments),
        "dynamic_batch_rows": len(batches),
        "maximum_authorized_date": dates.max().date().isoformat(),
        "absolute_account_identities_reconciled": True,
        "relative_benchmark_identities_reconciled": True,
        "annual_and_inventory_partitions_reconciled": True,
        "dynamic_overlay_batches_reconciled": True,
        "fee_breakdown_reconciled": True,
        "cash_yield_confirmed_zero": True,
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "output_hashes": output_hashes,
        "stage10_result_sha256": sha256(RESULT),
    }
    with VALIDATION.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
