"""One-shot, exposure-only calibration for HD-ANCHOR-001 Stage 8.

The authorized execution emits and freezes only w_bar, q_raw, and q_RM as
calibrated values. Daily weights and all economic-performance series remain
in memory and are never serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal, getcontext
from pathlib import Path


getcontext().prec = 28

TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TOPIC_ROOT))

from engine.stage8_engine import (  # noqa: E402
    DailyCloseLaggedEngine,
    DividendTaxSchedule,
    HDAnchorStrategy,
    PITDividendSelector,
    SHANGHAI_TZ,
    TransactionCostSchedule,
    dec,
    initialize_research_account,
    load_corporate_actions,
    load_sessions,
)


EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
DATASETS = TOPIC_ROOT / "datasets"
DESIGN_PATH = EXPERIMENT / "baseline_design_v1.0_frozen.json"
IMPLEMENTATION_MANIFEST_PATH = EXPERIMENT / "stage8_implementation_manifest_v1.0.json"
AUTHORIZATION_PATH = EXPERIMENT / "EXPOSURE_CALIBRATION_AUTHORIZATION_2026-09-13.md"
OUTPUT_PATH = EXPERIMENT / "baseline_calibration_v1.0_pre_oos.json"
ATTEMPT_PATH = EXPERIMENT / "baseline_calibration_attempt_v1.0_pre_oos.json"

START = date(2019, 3, 11)
END = date(2022, 3, 10)
LAST = date(2022, 3, 9)
EXPECTED_SESSIONS = 729
EXPECTED_TRADING = 719
EXPECTED_SUSPENDED = 10
EXPECTED_PRICE = Decimal("16.47")
COMMON_ASSETS = Decimal("60000")
INITIAL_SHARES = 1000
OOS_PRICE = Decimal("22.71")
CENT = Decimal("0.01")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise AssertionError(f"manifest path escapes repository: {relative}") from exc
    return path


def verify_items(items: list[dict[str, object]], label: str) -> None:
    for item in items:
        target = repo_path(str(item["path"]))
        if not target.is_file():
            raise AssertionError(f"{label} file missing: {item['path']}")
        actual = sha256(target)
        if actual != item["sha256"]:
            raise AssertionError(f"{label} hash mismatch: {item['path']}")


def load_and_preflight() -> dict[str, object]:
    if OUTPUT_PATH.exists() or ATTEMPT_PATH.exists():
        raise AssertionError("one-shot calibration artifact or attempt record already exists")
    if not AUTHORIZATION_PATH.is_file():
        raise AssertionError("explicit calibration authorization record is missing")

    design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    implementation = json.loads(IMPLEMENTATION_MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_items(design["inputs"], "frozen baseline input")
    implementation_items = implementation["parent_frozen_inputs"] + implementation["implementation_files"]
    verify_items(implementation_items, "Stage 8 implementation")

    derivation = design["risk_matching_derivation"]
    if derivation["calibration_start_inclusive"] != START.isoformat():
        raise AssertionError("calibration start differs from frozen design")
    if derivation["calibration_end_exclusive"] != END.isoformat():
        raise AssertionError("calibration end differs from frozen design")
    if derivation["calibration_calendar_sessions"] != EXPECTED_SESSIONS:
        raise AssertionError("frozen calibration session count changed")
    if derivation["calibration_price_ref_cny"] != float(EXPECTED_PRICE):
        raise AssertionError("frozen calibration price changed")

    fee_schedule = TransactionCostSchedule.from_csv(
        DATASETS / "schedules" / "a_share_transaction_cost_schedule_v2_pre2012.csv"
    )
    tax_schedule = DividendTaxSchedule.from_csv(
        DATASETS / "schedules" / "prc_listed_dividend_tax_schedule_v1.csv"
    )
    all_sessions = load_sessions(DATASETS / "cleaned" / "cleaned_price.csv")
    sessions = tuple(item for item in all_sessions if START <= item.session_date < END)
    trading = sum(item.trade_status == "TRADING" for item in sessions)
    suspended = sum(item.trade_status == "SUSPENDED_OR_MISSING" for item in sessions)
    if len(sessions) != EXPECTED_SESSIONS or trading != EXPECTED_TRADING or suspended != EXPECTED_SUSPENDED:
        raise AssertionError("calibration window status counts differ from frozen design")
    if sessions[0].session_date != START or sessions[-1].session_date != LAST:
        raise AssertionError("calibration window boundary sessions differ from frozen design")
    if sessions[0].close != EXPECTED_PRICE or sessions[0].trade_status != "TRADING":
        raise AssertionError("calibration initialization close is invalid")
    if sessions[1].session_date != date(2019, 3, 12) or sessions[2].session_date != date(2019, 3, 13):
        raise AssertionError("first signal/fill session anchors differ from frozen design")
    if any(item.trade_status not in {"TRADING", "SUSPENDED_OR_MISSING"} for item in sessions):
        raise AssertionError("unexpected trade status in calibration window")

    for item in sessions:
        if item.trade_status == "TRADING":
            if item.close is None or item.limit_up is None or item.limit_down is None:
                raise AssertionError(f"incomplete tradable session: {item.session_date}")
            fee_schedule.calculate(item.session_date, "BUY", 100, item.close)
            fee_schedule.calculate(item.session_date, "SELL", 100, item.close)

    pit_selector = PITDividendSelector.from_csv(
        DATASETS / "cleaned" / "point_in_time_dividend_estimates.csv"
    )
    actions = load_corporate_actions(DATASETS / "cleaned" / "corporate_actions.csv")
    if len(actions) != 25:
        raise AssertionError("ordinary-share action count differs from Stage 8 L0 freeze")
    if any(action.record_date < START <= action.pay_date for action in actions):
        raise AssertionError("unexpected cross-period dividend entitlement at calibration start")
    calendar_dates = {item.session_date for item in sessions}
    for action in actions:
        if START <= action.ex_date < END:
            if not {action.record_date, action.ex_date, action.pay_date}.issubset(calendar_dates):
                raise AssertionError(f"corporate-action date is absent from the calibration calendar: {action.action_id}")
            tax_schedule.select(action.tax_rule_version, action.ex_date, action.ex_date)

    return {
        "design": design,
        "implementation": implementation,
        "implementation_items": implementation_items,
        "fee_schedule": fee_schedule,
        "tax_schedule": tax_schedule,
        "sessions": sessions,
        "pit_selector": pit_selector,
        "actions": actions,
    }


def write_exclusive_json(path: Path, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def equity_weight(shares: int, mark: Decimal, nav: Decimal) -> Decimal:
    if nav <= 0:
        raise AssertionError("non-positive account value prevents exposure calibration")
    return dec(shares) * mark / nav


def execute_once(preflight: dict[str, object]) -> dict[str, object]:
    started_at = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
    attempt = {
        "statement_type": "已观察事实",
        "experiment_id": "HD-ANCHOR-001",
        "attempt_version": "HD-STAGE8-EXPOSURE-CALIBRATION-ATTEMPT-1.0-PRE-OOS",
        "started_at": started_at,
        "timezone": "Asia/Shanghai",
        "authorization_path": AUTHORIZATION_PATH.relative_to(REPO_ROOT).as_posix(),
        "authorization_sha256": sha256(AUTHORIZATION_PATH),
        "scope": "ONE_EXPOSURE_ONLY_DEVELOPMENT_VALIDATION_CALIBRATION",
        "maximum_attempts": 1,
    }
    write_exclusive_json(ATTEMPT_PATH, attempt)

    fee_schedule = preflight["fee_schedule"]
    tax_schedule = preflight["tax_schedule"]
    sessions = preflight["sessions"]
    account = initialize_research_account(
        common_assets=COMMON_ASSETS,
        shares=INITIAL_SHARES,
        price_ref=EXPECTED_PRICE,
        t0=START,
        initial_session_index=0,
        fee_schedule=fee_schedule,
        tax_schedule=tax_schedule,
    )
    if account.cash != Decimal("43530.0000") or account.nav(EXPECTED_PRICE) != Decimal("60000.0000"):
        raise AssertionError("calibration account initialization differs from frozen design")

    engine = DailyCloseLaggedEngine(
        account=account,
        initial_mark=EXPECTED_PRICE,
        initial_date=START,
        pit_selector=preflight["pit_selector"],
        strategy=HDAnchorStrategy(),
        corporate_actions=preflight["actions"],
        reconciliation_tolerance=CENT,
    )

    weights = [equity_weight(account.shares, EXPECTED_PRICE, account.nav(EXPECTED_PRICE))]
    for session_index, session in enumerate(sessions[1:], start=1):
        snapshot = engine.step(session, session_index, fundamental_gate="NORMAL")
        if abs(snapshot.reconciliation_difference) > CENT:
            raise AssertionError(f"daily reconciliation failed: {snapshot.session_date}")
        weights.append(equity_weight(snapshot.shares, snapshot.mark, snapshot.nav))
    if len(weights) != EXPECTED_SESSIONS:
        raise AssertionError("daily exposure observation count mismatch")

    w_bar = sum(weights, Decimal("0")) / Decimal(len(weights))
    q_raw = w_bar * COMMON_ASSETS / OOS_PRICE
    allowed_grid = preflight["design"]["baselines"][2]["allowed_share_grid"]
    feasible = [q for q in allowed_grid if COMMON_ASSETS - dec(q) * OOS_PRICE >= 0]
    if not feasible:
        raise AssertionError("no cash-nonnegative risk-matched share choice")
    q_rm = min(feasible, key=lambda q: (abs(dec(q) - q_raw), q))

    values = {
        "w_bar": str(w_bar),
        "q_raw": str(q_raw),
        "q_RM": q_rm,
    }
    completed_at = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
    output = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE8-EXPOSURE-CALIBRATION-1.0-PRE-OOS",
        "completed_at": completed_at,
        "timezone": "Asia/Shanghai",
        "status": "FROZEN_PRE_OOS_EXPOSURE_ONLY",
        "calibrated_values": values,
        "calibration_scope": {
            "window": "[2019-03-11, 2022-03-10)",
            "profile": "P00",
            "fundamental_gate": "NORMAL",
            "session_observations": EXPECTED_SESSIONS,
            "trading_sessions": EXPECTED_TRADING,
            "suspended_or_missing_sessions": EXPECTED_SUSPENDED,
            "daily_values_serialized": False,
        },
        "method": {
            "w_bar": "arithmetic_mean_of_post_accounting_daily_equity_weights",
            "q_raw": "w_bar*60000/22.71",
            "q_RM": "nearest_cash_nonnegative_100_share_grid_value_tie_lower",
            "decimal_precision": getcontext().prec,
        },
        "input_bindings": {
            "authorization": {
                "path": AUTHORIZATION_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256(AUTHORIZATION_PATH),
            },
            "calibration_runner": {
                "path": Path(__file__).resolve().relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256(Path(__file__).resolve()),
            },
            "baseline_design": {
                "path": DESIGN_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256(DESIGN_PATH),
            },
            "stage8_implementation_manifest": {
                "path": IMPLEMENTATION_MANIFEST_PATH.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256(IMPLEMENTATION_MANIFEST_PATH),
            },
            "frozen_baseline_inputs": preflight["design"]["inputs"],
            "verified_stage8_files": preflight["implementation_items"],
        },
        "integrity": {
            "frozen_baseline_input_hashes_checked": len(preflight["design"]["inputs"]),
            "stage8_file_hashes_checked": len(preflight["implementation_items"]),
            "daily_reconciliation": "PASS_ALL_OBSERVATIONS_WITHIN_CNY_0.01",
            "serialized_calibrated_value_count": 3,
        },
        "authorization_and_counters": {
            "exposure_calibration_authorized": True,
            "exposure_calibration_run_count": 1,
            "formal_backtest_run_count": 0,
            "performance_calculation_count": 0,
            "historical_pseudo_lock_open_count": 0,
            "prospective_lock_open_count": 0,
            "paper_trading_authorized": False,
            "live_trading_authorized": False,
            "dry_run": True,
        },
        "evidence_ceiling": "L0",
        "economic_conclusion": "NOT_AVAILABLE",
    }
    write_exclusive_json(OUTPUT_PATH, output)
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-authorized-once", action="store_true")
    args = parser.parse_args()

    preflight = load_and_preflight()
    if args.preflight:
        print(json.dumps({
            "status": "PASS_READY_FOR_ONE_AUTHORIZED_EXPOSURE_CALIBRATION",
            "frozen_baseline_input_hashes_checked": len(preflight["design"]["inputs"]),
            "stage8_file_hashes_checked": len(preflight["implementation_items"]),
            "session_observations": len(preflight["sessions"]),
        }, ensure_ascii=False, indent=2))
        return 0

    values = execute_once(preflight)
    print(json.dumps(values, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
