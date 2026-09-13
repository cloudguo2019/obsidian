"""Non-performance validator for the HD-ANCHOR-001 Stage 8 engine.

The validator checks immutable input hashes, loader/schema compatibility, dated
fee/tax coverage, and frozen initialization arithmetic.  It never instantiates a
dynamic historical strategy run and never computes returns or risk statistics.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TOPIC_ROOT))

from engine.stage8_engine import (  # noqa: E402
    DividendTaxSchedule,
    PITDividendSelector,
    TransactionCostSchedule,
    initialize_research_account,
    load_corporate_actions,
    load_sessions,
)


EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
DATASETS = TOPIC_ROOT / "datasets"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    checks: list[str] = []
    design = json.loads((EXPERIMENT / "baseline_design_v1.0_frozen.json").read_text(encoding="utf-8"))
    data_manifest = json.loads((DATASETS / "cleaned" / "data_manifest.json").read_text(encoding="utf-8"))

    for item in design["inputs"]:
        target = REPO_ROOT / item["path"]
        if not target.is_file() or sha256(target) != item["sha256"]:
            raise AssertionError(f"frozen input hash mismatch: {item['path']}")
    checks.append(f"frozen_input_hashes:{len(design['inputs'])}")

    fee_schedule = TransactionCostSchedule.from_csv(
        DATASETS / "schedules" / "a_share_transaction_cost_schedule_v2_pre2012.csv"
    )
    tax_schedule = DividendTaxSchedule.from_csv(
        DATASETS / "schedules" / "prc_listed_dividend_tax_schedule_v1.csv"
    )
    sessions = load_sessions(DATASETS / "cleaned" / "cleaned_price.csv")
    pit = PITDividendSelector.from_csv(DATASETS / "cleaned" / "point_in_time_dividend_estimates.csv")
    actions = load_corporate_actions(DATASETS / "cleaned" / "corporate_actions.csv")

    expected = data_manifest["row_counts"]
    if len(sessions) != expected["cleaned_price"]:
        raise AssertionError("cleaned price row count mismatch")
    if len(pit.records) != expected["point_in_time_dividend_estimates"]:
        raise AssertionError("PIT row count mismatch")
    # The source contains 25 distributions.  Four differential distributions
    # have an extra mutually-exclusive class row and one non-dividend row is
    # quarantined; the ordinary-share loader must therefore return 25 actions.
    if len(actions) != 25:
        raise AssertionError("ordinary-share cash-dividend action count mismatch")
    if any(action.action_id.endswith("-ASSET") or action.action_id.endswith("-EXCLUDED") for action in actions):
        raise AssertionError("mutually exclusive non-ordinary share class entered the account loader")
    participating_2022 = [action for action in actions if action.action_id.endswith("20230721-PARTICIPATING")]
    if len(participating_2022) != 1 or participating_2022[0].cash_dividend_per_share != Decimal("0.8533"):
        raise AssertionError("2022 differential dividend did not resolve to ordinary participating shares")
    checks.append("loader_schema_and_row_counts")

    for item in sessions:
        if item.trade_status == "TRADING" and item.close is not None:
            fee_schedule.calculate(item.session_date, "BUY", 100, item.close)
            fee_schedule.calculate(item.session_date, "SELL", 100, item.close)
    checks.append("transaction_fee_date_coverage_all_trading_sessions")

    for action in actions:
        if action.ex_date >= date(2015, 9, 8):
            tax_schedule.select(action.tax_rule_version, action.ex_date, action.ex_date)
    checks.append("dividend_tax_rule_coverage_stage8_economic_window")

    by_date = {item.session_date: item for item in sessions}
    main_t0 = date.fromisoformat(design["initialization"]["formal_oos_start_inclusive"])
    price_ref = by_date[main_t0].close
    if price_ref != Decimal(str(design["initialization"]["main_oos_price_ref_cny"])):
        raise AssertionError("formal t0 price reference mismatch")
    for shares, expected_cash in ((1000, Decimal("37290")), (1500, Decimal("25935"))):
        account = initialize_research_account(
            common_assets=design["initialization"]["common_initial_assets_cny"],
            shares=shares,
            price_ref=price_ref,
            t0=main_t0,
            initial_session_index=0,
            fee_schedule=fee_schedule,
            tax_schedule=tax_schedule,
        )
        if account.cash != expected_cash or account.nav(price_ref) != Decimal("60000"):
            raise AssertionError(f"initialization mismatch for {shares} shares")
    checks.append("frozen_static_initializations_without_fictitious_orders")

    output = {
        "statement_type": "计算结果",
        "validator": "HD-STAGE8-NON-PERFORMANCE-VALIDATOR-1.0",
        "status": "PASS",
        "checks": checks,
        "counts": {
            "frozen_input_hashes": len(design["inputs"]),
            "price_sessions": len(sessions),
            "pit_records": len(pit.records),
            "valid_cash_dividend_actions": len(actions),
        },
        "forbidden_outputs_generated": [],
        "formal_backtest_run_count_increment": 0,
        "exposure_calibration_run_count_increment": 0,
        "performance_calculation_count_increment": 0,
        "historical_pseudo_lock_open_count_increment": 0,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
