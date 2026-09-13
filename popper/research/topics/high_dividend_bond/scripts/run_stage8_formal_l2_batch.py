"""One-shot authorized retrospective L2 batch for HD-ANCHOR-001 Stage 8.

The executable boundary is deliberately narrower than the available dataset:
price rows are parsed only for [2022-03-10, 2025-09-10).  The later historical
pseudo-lock is neither evaluated nor serialized by this runner.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import traceback
from datetime import date, datetime
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Iterable, Mapping, Sequence


getcontext().prec = 28

TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TOPIC_ROOT))

from engine.stage8_batch import (  # noqa: E402
    FillAudit,
    FormalPathEngine,
    MarketSession,
    PathPoint,
    ProfilePITSelector,
    ProfileSpec,
    ProfileStrategy,
    ScaledTransactionCostSchedule,
    initial_path_point,
    load_market_sessions,
    load_session_dates,
    path_metrics,
    registered_profiles,
    shifted_strategy_config,
    snapshot_path_point,
    window_effects,
)
from engine.stage8_engine import (  # noqa: E402
    CorporateAction,
    DividendTaxSchedule,
    PITDividendRecord,
    SHANGHAI_TZ,
    TransactionCostSchedule,
    ZERO,
    dec,
    initialize_research_account,
    parse_datetime,
    required_date,
    shanghai_close,
)


EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
DATASETS = TOPIC_ROOT / "datasets"
PRICE_PATH = DATASETS / "cleaned" / "cleaned_price.csv"
PIT_PATH = DATASETS / "cleaned" / "point_in_time_dividend_estimates.csv"
ACTIONS_PATH = DATASETS / "cleaned" / "corporate_actions.csv"
FEE_PATH = DATASETS / "schedules" / "a_share_transaction_cost_schedule_v2_pre2012.csv"
TAX_PATH = DATASETS / "schedules" / "prc_listed_dividend_tax_schedule_v1.csv"

PROTOCOL_PATH = EXPERIMENT / "preregistration.yaml"
SPLIT_PARENT_PATH = EXPERIMENT / "sample_split_v1.0_pending_confirmation.json"
SPLIT_PATH = EXPERIMENT / "sample_split_v1.1_frozen_with_exposure_classification.json"
BASELINE_DESIGN_PATH = EXPERIMENT / "baseline_design_v1.0_frozen.json"
STAGE8_IMPLEMENTATION_MANIFEST_PATH = EXPERIMENT / "stage8_implementation_manifest_v1.0.json"
CALIBRATION_MANIFEST_PATH = EXPERIMENT / "baseline_calibration_manifest_v1.0_pre_oos.json"
CALIBRATION_RESULT_PATH = EXPERIMENT / "baseline_calibration_v1.0_pre_oos.json"
AUTHORIZATION_PATH = EXPERIMENT / "FORMAL_L2_AUTHORIZATION_2026-09-13.md"
BATCH_IMPLEMENTATION_MANIFEST_PATH = (
    EXPERIMENT / "stage8_formal_batch_implementation_manifest_v1.0.json"
)

ATTEMPT_PATH = EXPERIMENT / "formal_l2_attempt_v1.0_prelock.json"
RESULT_PATH = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
FAILURE_PATH = EXPERIMENT / "formal_l2_failure_v1.0_prelock.json"
OUTPUT_DIR = EXPERIMENT / "formal_l2_v1.0_prelock"

START = date(2022, 3, 10)
END = date(2025, 9, 10)
LAST = date(2025, 9, 9)
EXPECTED_OBSERVATIONS = 852
EXPECTED_TRADING = 851
EXPECTED_SUSPENDED = 1
COMMON_ASSETS = Decimal("60000")
RISK_MATCHED_SHARES = 900
RECONCILIATION_TOLERANCE = Decimal("0.01")
BOOTSTRAP_SEED = 20260905
BOOTSTRAP_REPLICATIONS = 5000
BOOTSTRAP_BLOCK_LENGTHS = (20, 60, 120)
ACCOUNT_SPECS = (
    ("HD-ANCHOR-001", None),
    ("HD-BASE-000", 1000),
    ("HD-BASE-001", 1500),
    ("HD-BASE-RM-001", RISK_MATCHED_SHARES),
)
OUTPUT_RELATIVE_NAMES = (
    "daily_accounts.parquet",
    "daily_close_signal_and_lagged_orders.parquet",
    "auction_outcomes_daily_close_lagged.parquet",
    "run_ledger.json",
    "profile_results.json",
    "window_results.json",
    "bootstrap_intervals.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def repo_path(relative: str) -> Path:
    target = (REPO_ROOT / relative).resolve()
    try:
        target.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise AssertionError(f"manifest path escapes repository: {relative}") from exc
    return target


def verify_items(items: Iterable[Mapping[str, object]], label: str) -> int:
    count = 0
    for item in items:
        target = repo_path(str(item["path"]))
        if not target.is_file():
            raise AssertionError(f"{label} file missing: {item['path']}")
        if sha256(target) != item["sha256"]:
            raise AssertionError(f"{label} hash mismatch: {item['path']}")
        count += 1
    return count


def write_exclusive_json(path: Path, payload: object) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def load_pit_records_before_end(path: Path, end_exclusive: date) -> tuple[PITDividendRecord, ...]:
    """Parse only PIT records whose availability can affect the authorized window."""

    records: list[PITDividendRecord] = []
    previous_available: datetime | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            available = parse_datetime(row["available_time"])
            if previous_available is not None and available < previous_available:
                raise AssertionError("PIT records are not ordered by available_time")
            previous_available = available
            if available.date() >= end_exclusive:
                break
            records.append(PITDividendRecord(
                record_id=row["record_id"],
                available_time=available,
                effective_time=parse_datetime(row["effective_time"]),
                expiry_time=parse_datetime(row["expiry_time"]),
                superseded_time=(
                    parse_datetime(row["superseded_time"])
                    if row["superseded_time"]
                    else None
                ),
                dps=dec(row["expected_annual_dividend_per_share"]),
                method=row["estimate_method"],
            ))
    if not records:
        raise AssertionError("no PIT records were available before the authorized end")
    return tuple(records)


def load_actions_before_end(path: Path, end_exclusive: date) -> tuple[CorporateAction, ...]:
    """Load ordinary-share actions with record dates before the authorized end."""

    raw_rows: list[dict[str, str]] = []
    previous_record_date: date | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            record_date = required_date(row["record_date"], "record_date")
            if previous_record_date is not None and record_date < previous_record_date:
                raise AssertionError("corporate actions are not ordered by record_date")
            previous_record_date = record_date
            if record_date >= end_exclusive:
                break
            if row["record_status"] == "VALID" and row["action_type"] == "CASH_DIVIDEND":
                raw_rows.append(dict(row))

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in raw_rows:
        grouped.setdefault(row["action_group_id"], []).append(row)

    selected: list[dict[str, str]] = []
    for group_id, group in grouped.items():
        preferred = [
            row for row in group
            if row["action_id"].endswith("-ORDINARY")
            or row["action_id"].endswith("-PARTICIPATING")
        ]
        if len(preferred) == 1:
            selected.append(preferred[0])
            continue
        eligible = [
            row for row in group
            if dec(row["cash_dividend_per_share"]) > ZERO
            and not row["tax_rule_version"].startswith("NOT_APPLICABLE")
        ]
        if len(eligible) != 1:
            raise AssertionError(f"ordinary-share entitlement is ambiguous: {group_id}")
        selected.append(eligible[0])

    return tuple(CorporateAction(
        action_id=row["action_id"],
        record_date=required_date(row["record_date"], "record_date"),
        ex_date=required_date(row["ex_date"], "ex_date"),
        pay_date=required_date(row["pay_date"], "pay_date"),
        cash_dividend_per_share=dec(row["cash_dividend_per_share"]),
        tax_rule_version=row["tax_rule_version"],
        share_transfer_per_share=(
            dec(row["share_transfer_per_share"])
            if row["share_transfer_per_share"]
            else ZERO
        ),
    ) for row in selected)


def load_and_preflight() -> dict[str, object]:
    if ATTEMPT_PATH.exists() or RESULT_PATH.exists() or FAILURE_PATH.exists() or OUTPUT_DIR.exists():
        raise AssertionError("one-shot formal batch attempt or output already exists")
    if not AUTHORIZATION_PATH.is_file():
        raise AssertionError("formal L2 authorization record is missing")
    if not BATCH_IMPLEMENTATION_MANIFEST_PATH.is_file():
        raise AssertionError("formal batch implementation manifest is missing")

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    split_parent = json.loads(SPLIT_PARENT_PATH.read_text(encoding="utf-8"))
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    baseline_design = json.loads(BASELINE_DESIGN_PATH.read_text(encoding="utf-8"))
    calibration = json.loads(CALIBRATION_RESULT_PATH.read_text(encoding="utf-8"))
    batch_manifest = json.loads(BATCH_IMPLEMENTATION_MANIFEST_PATH.read_text(encoding="utf-8"))
    implementation_manifest = json.loads(
        STAGE8_IMPLEMENTATION_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    calibration_manifest = json.loads(CALIBRATION_MANIFEST_PATH.read_text(encoding="utf-8"))

    batch_hash_checks = verify_items(
        batch_manifest["parent_frozen_inputs"] + batch_manifest["implementation_files"],
        "formal batch implementation binding",
    )
    frozen_stage8_hash_checks = verify_items(
        implementation_manifest["parent_frozen_inputs"]
        + implementation_manifest["implementation_files"],
        "frozen Stage 8 implementation",
    )
    calibration_hash_checks = verify_items(
        calibration_manifest["parent_bindings"] + calibration_manifest["calibration_files"],
        "frozen exposure calibration",
    )

    if calibration["calibrated_values"]["q_RM"] != RISK_MATCHED_SHARES:
        raise AssertionError("risk-matched baseline is not the frozen 900-share value")
    protocol_ids = tuple(item["id"] for item in protocol["experiment_budget"]["profiles"])
    profiles = registered_profiles()
    if tuple(item.profile_id for item in profiles) != protocol_ids:
        raise AssertionError("registered batch profiles differ from the frozen budget")
    if len(profiles) * len(ACCOUNT_SPECS) != 96:
        raise AssertionError("formal path registry is not exactly 96 paths")
    if profiles[21].runnable or profiles[21].not_run_reason != (
        "NO_AUDITABLE_EXECUTABLE_BROKER_CASH_RATE_INPUT"
    ):
        raise AssertionError("P21 must fail closed without a broker cash-rate input")

    windows = [
        item for item in split_parent["historical_windows"]
        if item["role"] == "retrospective_rolling_oos"
    ]
    if len(windows) != 7:
        raise AssertionError("authorized retrospective window count is not seven")
    if windows[0]["start_inclusive"] != START.isoformat() or windows[-1]["end_exclusive"] != END.isoformat():
        raise AssertionError("authorized retrospective window boundaries changed")
    if any(item["id"].startswith("PLOCK") for item in windows):
        raise AssertionError("pseudo-lock window was selected by preflight")
    if split["historical_evidence_identity"]["historical_sealed_period_start_inclusive"] != END.isoformat():
        raise AssertionError("historical pseudo-lock boundary changed")

    sessions = load_market_sessions(PRICE_PATH, start_inclusive=START, end_exclusive=END)
    trading = sum(item.trade_status == "TRADING" for item in sessions)
    suspended = sum(item.trade_status == "SUSPENDED_OR_MISSING" for item in sessions)
    if (len(sessions), trading, suspended) != (
        EXPECTED_OBSERVATIONS, EXPECTED_TRADING, EXPECTED_SUSPENDED
    ):
        raise AssertionError("authorized price-session counts differ from the frozen split")
    if sessions[0].session_date != START or sessions[-1].session_date != LAST:
        raise AssertionError("authorized price boundaries differ from the frozen split")
    expected_starts = {
        date(2022, 3, 10): Decimal("22.71"),
        date(2022, 6, 10): Decimal("24.02"),
        date(2022, 9, 13): Decimal("23.79"),
    }
    by_date = {item.session_date: item for item in sessions}
    for start_date, expected_close in expected_starts.items():
        item = by_date.get(start_date)
        if item is None or item.trade_status != "TRADING" or item.close != expected_close:
            raise AssertionError(f"invalid registered initialization anchor: {start_date}")
    if any(item.session_date >= END for item in sessions):
        raise AssertionError("unauthorized price row entered the formal batch")

    fee_schedule = TransactionCostSchedule.from_csv(FEE_PATH)
    tax_schedule = DividendTaxSchedule.from_csv(TAX_PATH)
    for item in sessions:
        if item.trade_status == "TRADING":
            if any(value is None for value in (item.open, item.close, item.limit_up, item.limit_down)):
                raise AssertionError(f"incomplete tradable session: {item.session_date}")
            fee_schedule.calculate(item.session_date, "BUY", 100, item.close)
            fee_schedule.calculate(item.session_date, "SELL", 100, item.close)
        elif item.trade_status != "SUSPENDED_OR_MISSING":
            raise AssertionError(f"unexpected trade status: {item.trade_status}")

    all_session_dates = load_session_dates(PRICE_PATH, end_exclusive=END)
    if not all_session_dates or all_session_dates[-1] != LAST:
        raise AssertionError("bounded session calendar did not stop at the authorized end")
    pit_records = load_pit_records_before_end(PIT_PATH, END)
    actions = load_actions_before_end(ACTIONS_PATH, END)
    session_date_set = set(all_session_dates)
    profile_start_dates = {item.start_date for item in profiles if item.runnable}
    for start_date in profile_start_dates:
        if any(action.record_date < start_date <= action.pay_date for action in actions):
            raise AssertionError(f"cross-period entitlement at {start_date}")
        if any(start_date in {action.record_date, action.ex_date, action.pay_date} for action in actions):
            raise AssertionError(f"initialization date overlaps a corporate-action event: {start_date}")
    for action in actions:
        if START <= action.ex_date < END:
            if not {action.record_date, action.ex_date, action.pay_date}.issubset(session_date_set):
                raise AssertionError(f"corporate-action date is outside the bounded calendar: {action.action_id}")
            tax_schedule.select(action.tax_rule_version, action.ex_date, action.ex_date)

    return {
        "protocol": protocol,
        "split_parent": split_parent,
        "split": split,
        "baseline_design": baseline_design,
        "calibration": calibration,
        "batch_manifest": batch_manifest,
        "profiles": profiles,
        "windows": windows,
        "sessions": sessions,
        "all_session_dates": all_session_dates,
        "pit_records": pit_records,
        "actions": actions,
        "fee_schedule": fee_schedule,
        "tax_schedule": tax_schedule,
        "hash_checks": {
            "formal_batch_bindings": batch_hash_checks,
            "frozen_stage8_bindings": frozen_stage8_hash_checks,
            "calibration_bindings": calibration_hash_checks,
        },
    }


def point_row(point: PathPoint) -> dict[str, object]:
    return {
        "profile_id": point.profile_id,
        "account_id": point.account_id,
        "session_date": point.session_date.isoformat(),
        "session_index": point.session_index,
        "trade_status": point.trade_status,
        "mark_cny": str(point.mark),
        "cash_cny": str(point.cash),
        "shares": point.shares,
        "available_shares": point.available_shares,
        "dividend_receivable_cny": str(point.dividend_receivable),
        "tax_liability_cny": str(point.tax_liability),
        "nav_cny": str(point.nav),
        "daily_return": decimal_string(point.daily_return),
        "drawdown": str(point.drawdown),
        "equity_weight": str(point.equity_weight),
        "cash_ratio": str(point.cash_ratio),
        "price_pnl_cny": str(point.price_pnl),
        "execution_price_pnl_cny": str(point.execution_price_pnl),
        "new_dividend_entitlement_cny": str(point.new_dividend_entitlement),
        "dividend_paid_gross_cny": str(point.dividend_paid_gross),
        "tax_reserve_change_cny": str(point.tax_reserve_change),
        "transaction_fees_cny": str(point.transaction_fees),
        "expected_nav_change_cny": str(point.expected_nav_change),
        "actual_nav_change_cny": str(point.actual_nav_change),
        "reconciliation_difference_cny": str(point.reconciliation_difference),
        "signal_blocker": point.signal_blocker,
        "selected_pit_record_id": point.selected_pit_record_id,
    }


def signal_row(
    profile: ProfileSpec,
    session: MarketSession,
    session_index: int,
    snapshot: object | None,
    profile_sessions: Sequence[MarketSession],
) -> dict[str, object]:
    if snapshot is None:
        return {
            "profile_id": profile.profile_id,
            "session_date": session.session_date.isoformat(),
            "session_index": session_index,
            "trade_status": session.trade_status,
            "decision_time": shanghai_close(session.session_date).isoformat(),
            "decision_close_cny": decimal_string(session.close),
            "selected_pit_record_id": None,
            "signal_blocker": "INITIALIZATION_NO_SIGNAL",
            "generated_order_id": None,
            "order_reason": None,
            "original_shares": None,
            "target_shares": None,
            "decision_dps_cny": None,
            "execute_session_index": None,
            "execute_session_date": None,
            "fill_field": profile.fill_field,
            "execution_lag_sessions": profile.execution_lag_sessions,
        }
    generated = snapshot.generated_order
    execute_date = None
    if generated is not None and generated.execute_session_index < len(profile_sessions):
        execute_date = profile_sessions[generated.execute_session_index].session_date.isoformat()
    return {
        "profile_id": profile.profile_id,
        "session_date": session.session_date.isoformat(),
        "session_index": session_index,
        "trade_status": session.trade_status,
        "decision_time": shanghai_close(session.session_date).isoformat(),
        "decision_close_cny": decimal_string(session.close),
        "selected_pit_record_id": snapshot.selected_pit_record_id,
        "signal_blocker": snapshot.signal_blocker,
        "generated_order_id": None if generated is None else generated.order_id,
        "order_reason": None if generated is None else generated.reason,
        "original_shares": None if generated is None else generated.original_shares,
        "target_shares": None if generated is None else generated.target_shares,
        "decision_dps_cny": None if generated is None else str(generated.decision_dps),
        "execute_session_index": None if generated is None else generated.execute_session_index,
        "execute_session_date": execute_date,
        "fill_field": profile.fill_field,
        "execution_lag_sessions": profile.execution_lag_sessions,
    }


def fill_row(profile: ProfileSpec, fill: FillAudit) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "account_id": "HD-ANCHOR-001",
        "order_id": fill.order_id,
        "session_date": fill.session_date.isoformat(),
        "session_index": fill.session_index,
        "status": fill.status,
        "reason": fill.reason,
        "side": fill.side,
        "requested_quantity": fill.requested_quantity,
        "filled_quantity": fill.filled_quantity,
        "fill_price_cny": decimal_string(fill.fill_price),
        "reference_price_cny": decimal_string(fill.reference_price),
        "fee_components_cny": json.dumps(
            {name: str(value) for name, value in sorted(fill.fees.components.items())},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "total_fees_cny": str(fill.fees.total),
        "deferred_tax_paid_cny": str(fill.deferred_tax_paid),
        "pre_shares": fill.pre_shares,
        "post_shares": fill.post_shares,
        "source_reason": fill.source_reason,
    }


def pit_coverage(
    selector: ProfilePITSelector,
    sessions: Sequence[MarketSession],
) -> tuple[int, int]:
    valid = 0
    decisions = 0
    for session in sessions:
        if session.trade_status != "TRADING" or session.close is None:
            continue
        decisions += 1
        record, _ = selector.select(shanghai_close(session.session_date))
        valid += record is not None
    return valid, decisions


def run_path(
    *,
    profile: ProfileSpec,
    account_id: str,
    initial_shares: int,
    profile_sessions: Sequence[MarketSession],
    selector: ProfilePITSelector | None,
    strategy: ProfileStrategy | None,
    fee_schedule: object,
    tax_schedule: DividendTaxSchedule,
    actions: Sequence[CorporateAction],
) -> dict[str, object]:
    start = profile_sessions[0]
    if start.close is None:
        raise AssertionError("path initialization lacks a close")
    account = initialize_research_account(
        common_assets=COMMON_ASSETS,
        shares=initial_shares,
        price_ref=start.close,
        t0=start.session_date,
        initial_session_index=0,
        fee_schedule=fee_schedule,
        tax_schedule=tax_schedule,
    )
    engine = FormalPathEngine(
        account=account,
        initial_mark=start.close,
        initial_date=start.session_date,
        profile=profile,
        pit_selector=selector,
        strategy=strategy,
        corporate_actions=actions,
        reconciliation_tolerance=RECONCILIATION_TOLERANCE,
    )
    points = [initial_path_point(
        profile_id=profile.profile_id,
        account_id=account_id,
        session=start,
        account=account,
    )]
    daily_rows = [point_row(points[0])]
    signals: list[dict[str, object]] = []
    if strategy is not None:
        signals.append(signal_row(profile, start, 0, None, profile_sessions))
    fills: list[FillAudit] = []
    outcomes: list[dict[str, object]] = []
    generated_order_count = 0
    high_water = points[0].nav

    for session_index, session in enumerate(profile_sessions[1:], start=1):
        previous_nav = points[-1].nav
        snapshot = engine.step(session, session_index, fundamental_gate="NORMAL")
        point = snapshot_path_point(
            profile_id=profile.profile_id,
            account_id=account_id,
            trade_status=session.trade_status,
            snapshot=snapshot,
            previous_nav=previous_nav,
            high_water=high_water,
        )
        high_water = max(high_water, point.nav)
        points.append(point)
        daily_rows.append(point_row(point))
        if strategy is not None:
            signals.append(signal_row(profile, session, session_index, snapshot, profile_sessions))
            generated_order_count += snapshot.generated_order is not None
            fills.extend(snapshot.fills)
            outcomes.extend(fill_row(profile, fill) for fill in snapshot.fills)

    pending_orders = [order for orders in engine.pending.values() for order in orders]
    for order in pending_orders:
        outcomes.append({
            "profile_id": profile.profile_id,
            "account_id": "HD-ANCHOR-001",
            "order_id": order.order_id,
            "session_date": None,
            "session_index": order.execute_session_index,
            "status": "PENDING_AT_TERMINAL",
            "reason": "EXECUTION_DATE_OUTSIDE_AUTHORIZED_WINDOW",
            "side": "BUY" if order.target_shares > order.original_shares else "SELL",
            "requested_quantity": abs(order.target_shares - order.original_shares),
            "filled_quantity": 0,
            "fill_price_cny": None,
            "reference_price_cny": None,
            "fee_components_cny": "{}",
            "total_fees_cny": "0",
            "deferred_tax_paid_cny": "0",
            "pre_shares": order.original_shares,
            "post_shares": order.original_shares,
            "source_reason": order.reason,
        })

    if selector is None:
        valid_pit = None
        pit_decisions = None
    else:
        valid_pit, pit_decisions = pit_coverage(selector, profile_sessions)
    metrics = path_metrics(
        points,
        fills,
        generated_order_count=generated_order_count,
        pending_at_terminal=len(pending_orders),
        pit_valid_decision_sessions=valid_pit,
        pit_decision_sessions=pit_decisions,
    )
    return {
        "points": points,
        "fills": fills,
        "daily_rows": daily_rows,
        "signal_rows": signals,
        "outcome_rows": outcomes,
        "metrics": metrics,
    }


def paired_returns(
    dynamic: Sequence[PathPoint], comparator: Sequence[PathPoint]
) -> tuple[list[date], list[Decimal], list[Decimal]]:
    dynamic_rows = [(item.session_date, item.daily_return) for item in dynamic if item.daily_return is not None]
    comparator_rows = [(item.session_date, item.daily_return) for item in comparator if item.daily_return is not None]
    if [item[0] for item in dynamic_rows] != [item[0] for item in comparator_rows]:
        raise AssertionError("dynamic and comparator daily returns are not date-aligned")
    return (
        [item[0] for item in dynamic_rows],
        [item[1] for item in dynamic_rows],
        [item[1] for item in comparator_rows],
    )


def profile_comparisons(paths: Mapping[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    dynamic_metrics = paths["HD-ANCHOR-001"]["metrics"]
    comparisons: dict[str, dict[str, object]] = {}
    for account_id in ("HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001"):
        comparator_metrics = paths[account_id]["metrics"]
        comparisons[account_id] = {
            "delta_cagr": str(
                dec(dynamic_metrics["cagr"]) - dec(comparator_metrics["cagr"])
            ),
            "delta_total_return": str(
                dec(dynamic_metrics["total_return"]) - dec(comparator_metrics["total_return"])
            ),
            "terminal_asset_difference_cny": str(
                dec(dynamic_metrics["final_nav_cny"]) - dec(comparator_metrics["final_nav_cny"])
            ),
            "max_drawdown_difference": str(
                dec(dynamic_metrics["max_drawdown"]) - dec(comparator_metrics["max_drawdown"])
            ),
            "absolute_mean_equity_weight_difference": str(abs(
                dec(dynamic_metrics["average_equity_weight"])
                - dec(comparator_metrics["average_equity_weight"])
            )),
        }
    return comparisons


def stationary_bootstrap_indices(
    rng: object, *, replications: int, observations: int, block_length: int
) -> object:
    import numpy as np

    indices = np.empty((replications, observations), dtype=np.int32)
    indices[:, 0] = rng.integers(0, observations, size=replications)
    restart_probability = 1.0 / float(block_length)
    for column in range(1, observations):
        restart = rng.random(replications) < restart_probability
        continued = (indices[:, column - 1] + 1) % observations
        fresh = rng.integers(0, observations, size=replications)
        indices[:, column] = np.where(restart, fresh, continued)
    return indices


def bootstrap_intervals(
    all_paths: Mapping[str, Mapping[str, dict[str, object]]],
) -> list[dict[str, object]]:
    import numpy as np

    lengths = sorted({
        len(path["points"]) - 1
        for paths in all_paths.values()
        for path in paths.values()
        if path["points"]
    })
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    index_cache = {
        (length, block): stationary_bootstrap_indices(
            rng,
            replications=BOOTSTRAP_REPLICATIONS,
            observations=length,
            block_length=block,
        )
        for length in lengths
        for block in BOOTSTRAP_BLOCK_LENGTHS
    }
    annualized_cache: dict[tuple[object, ...], object] = {}
    static_series: dict[tuple[str, str], tuple[Decimal, ...]] = {}
    output: list[dict[str, object]] = []

    def annualized(
        cache_key: tuple[object, ...],
        returns: Sequence[Decimal],
        years: float,
        block: int,
    ) -> object:
        key = cache_key + (block,)
        if key not in annualized_cache:
            values = np.asarray([float(item) for item in returns], dtype=np.float64)
            sampled_log_growth = np.log1p(values)[index_cache[(len(values), block)]].sum(axis=1)
            annualized_cache[key] = np.expm1(sampled_log_growth / years)
        return annualized_cache[key]

    for profile_id, paths in all_paths.items():
        dynamic_points = paths["HD-ANCHOR-001"]["points"]
        for account_id in ("HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001"):
            comparator_points = paths[account_id]["points"]
            dates, dynamic_returns, comparator_returns = paired_returns(
                dynamic_points, comparator_points
            )
            years = (dates[-1] - dynamic_points[0].session_date).days / 365.25
            if years <= 0:
                raise AssertionError("bootstrap path has non-positive duration")
            static_key = (dynamic_points[0].session_date.isoformat(), account_id)
            static_tuple = tuple(comparator_returns)
            if static_key in static_series and static_series[static_key] != static_tuple:
                raise AssertionError("static baseline differs across an identical start scenario")
            static_series.setdefault(static_key, static_tuple)
            point_delta = (
                dec(paths["HD-ANCHOR-001"]["metrics"]["cagr"])
                - dec(paths[account_id]["metrics"]["cagr"])
            )
            for block in BOOTSTRAP_BLOCK_LENGTHS:
                dynamic_cagr = annualized(
                    ("DYNAMIC", profile_id), dynamic_returns, years, block
                )
                comparator_cagr = annualized(
                    ("STATIC",) + static_key, comparator_returns, years, block
                )
                differences = dynamic_cagr - comparator_cagr
                lower, upper = np.quantile(differences, [0.025, 0.975], method="linear")
                output.append({
                    "profile_id": profile_id,
                    "comparator_id": account_id,
                    "paired_return_sessions": len(dates),
                    "elapsed_calendar_days": (
                        dynamic_points[-1].session_date - dynamic_points[0].session_date
                    ).days,
                    "point_delta_cagr": str(point_delta),
                    "expected_block_length_sessions": block,
                    "replications": BOOTSTRAP_REPLICATIONS,
                    "seed": BOOTSTRAP_SEED,
                    "ci_level": "0.95",
                    "ci_lower": format(float(lower), ".15g"),
                    "ci_upper": format(float(upper), ".15g"),
                    "status": (
                        "PASS_INFERENCE_SAMPLE_SIZE"
                        if len(dates) >= max(240, 4 * block)
                        else "INSUFFICIENT_FOR_RELIABLE_INFERENCE"
                    ),
                })
    return output


def annual_relative_diagnostics(
    dynamic: Sequence[PathPoint], comparator: Sequence[PathPoint]
) -> dict[str, object]:
    dates, dynamic_returns, comparator_returns = paired_returns(dynamic, comparator)
    by_year: dict[int, list[tuple[Decimal, Decimal]]] = {}
    for session_date, dynamic_return, comparator_return in zip(
        dates, dynamic_returns, comparator_returns
    ):
        by_year.setdefault(session_date.year, []).append((dynamic_return, comparator_return))
    rows = []
    for year, values in sorted(by_year.items()):
        dynamic_growth = Decimal("1")
        comparator_growth = Decimal("1")
        for dynamic_return, comparator_return in values:
            dynamic_growth *= Decimal("1") + dynamic_return
            comparator_growth *= Decimal("1") + comparator_return
        rows.append({
            "year": year,
            "paired_sessions": len(values),
            "dynamic_total_return": str(dynamic_growth - Decimal("1")),
            "comparator_total_return": str(comparator_growth - Decimal("1")),
            "increment": str(dynamic_growth - comparator_growth),
        })
    best = max(rows, key=lambda item: (dec(item["increment"]), -int(item["year"])))
    kept = [
        (session_date, dynamic_return, comparator_return)
        for session_date, dynamic_return, comparator_return in zip(
            dates, dynamic_returns, comparator_returns
        )
        if session_date.year != best["year"]
    ]
    dynamic_growth = Decimal("1")
    comparator_growth = Decimal("1")
    for _, dynamic_return, comparator_return in kept:
        dynamic_growth *= Decimal("1") + dynamic_return
        comparator_growth *= Decimal("1") + comparator_return
    return {
        "calendar_years": rows,
        "largest_positive_relative_year": best["year"],
        "exclude_largest_relative_year_remaining_total_return_increment": str(
            dynamic_growth - comparator_growth
        ),
        "exclude_largest_relative_year_status": "DESCRIPTIVE_NONCONTIGUOUS_DIAGNOSTIC",
    }


def write_parquet(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    if path.exists():
        raise FileExistsError(path)
    table = pa.Table.from_pylist(list(rows))
    pq.write_table(table, path, compression="zstd")


def evaluate_batch(
    profile_results: Mapping[str, dict[str, object]],
    bootstrap_rows: Sequence[Mapping[str, object]],
    signal_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    p00 = profile_results["P00"]
    metrics = p00["paths"]["HD-ANCHOR-001"]
    comparator_metrics = p00["paths"]["HD-BASE-RM-001"]
    comparison = p00["comparisons"]["HD-BASE-RM-001"]
    ci = {
        int(item["expected_block_length_sessions"]): item
        for item in bootstrap_rows
        if item["profile_id"] == "P00" and item["comparator_id"] == "HD-BASE-RM-001"
    }
    window_rows = p00["window_effects"]["HD-BASE-RM-001"]
    passed_windows = [item for item in window_rows if item["status"] == "PASS"]
    positive_windows = sum(dec(item["increment"]) > ZERO for item in passed_windows)
    positive_fraction = Decimal(positive_windows) / Decimal(len(passed_windows))
    risk_match_difference = dec(comparison["absolute_mean_equity_weight_difference"])
    dynamic_mdd = abs(dec(metrics["max_drawdown"]))
    comparator_mdd = abs(dec(comparator_metrics["max_drawdown"]))
    required_robustness = ("P01", "P03", "P05", "P06", "P10")
    required_robustness_nonnegative = all(
        dec(profile_results[item]["comparisons"]["HD-BASE-RM-001"]["delta_cagr"]) >= ZERO
        for item in required_robustness
    )
    local_neighborhood = ("P15", "P16", "P17", "P18")
    local_nonnegative_count = sum(
        dec(profile_results[item]["comparisons"]["HD-BASE-RM-001"]["delta_cagr"]) >= ZERO
        for item in local_neighborhood
    )
    p23_partial = profile_results["P23"]["paths"]["HD-ANCHOR-001"][
        "partially_filled_parent_orders"
    ]
    p23_stuck = any(
        item["profile_id"] == "P23" and item["signal_blocker"] == "ILLEGAL_DISCRETE_STATE_HOLD"
        for item in signal_rows
    )
    gates = {
        "daily_reconciliation": (
            "PASS" if all(
                dec(metrics_row["maximum_absolute_daily_reconciliation_cny"])
                <= RECONCILIATION_TOLERANCE
                for profile in profile_results.values()
                if profile["status"] == "COMPLETED"
                for metrics_row in profile["paths"].values()
            ) else "FAIL"
        ),
        "risk_matched_weight_difference_le_0_05": risk_match_difference <= Decimal("0.05"),
        "p00_delta_cagr_ge_0_005": dec(comparison["delta_cagr"]) >= Decimal("0.005"),
        "p00_primary_bootstrap_ci_lower_gt_0": dec(ci[60]["ci_lower"]) > ZERO,
        "p00_mdd_le_0_16": dynamic_mdd <= Decimal("0.16"),
        "p00_mdd_excess_over_rm_le_0_02": dynamic_mdd - comparator_mdd <= Decimal("0.02"),
        "p00_recovery_within_126_sessions": metrics["recovery_gate"] == "PASS",
        "p00_filled_parents_rolling_252_le_24": (
            metrics["maximum_filled_parent_orders_in_rolling_252_sessions"] <= 24
        ),
        "p00_filled_adjacent_transition_days_ge_20": (
            metrics["filled_adjacent_state_transition_days"] >= 20
        ),
        "p00_transition_clusters_ge_10": metrics["transition_clusters_20_session_gap"] >= 10,
        "p00_positive_six_month_window_fraction_ge_0_60": positive_fraction >= Decimal("0.60"),
        "registered_robustness_profiles_nonnegative": required_robustness_nonnegative,
        "local_parameter_neighbors_at_least_3_of_4_nonnegative": local_nonnegative_count >= 3,
        "block_20_and_120_no_ci_upper_below_zero": (
            dec(ci[20]["ci_upper"]) >= ZERO and dec(ci[120]["ci_upper"]) >= ZERO
        ),
        "p23_partial_fill_occurred": p23_partial > 0,
        "p23_non_round_state_stuck_exposed": p23_stuck,
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "prospective_clean_l3": "NOT_YET_AVAILABLE",
    }
    personal_failure = (
        not gates["p00_mdd_le_0_16"]
        or not gates["p00_mdd_excess_over_rm_le_0_02"]
        or metrics["recovery_gate"] == "FAIL_OVER_126_SESSIONS"
        or not gates["p00_filled_parents_rolling_252_le_24"]
    )
    implementation_issue = gates["daily_reconciliation"] != "PASS" or p23_stuck
    if implementation_issue or personal_failure:
        decision = "修改"
    else:
        decision = "观察"
    return {
        "decision": decision,
        "decision_scope": "RETROSPECTIVE_L2_PRELOCK_ONLY",
        "maximum_evidence_level": "L2",
        "acceptance_or_elimination_available": False,
        "reason": (
            "P23_PARTIAL_FILL_EXPOSED_NON_ROUND_STATE_STUCK"
            if p23_stuck
            else "PERSONAL_RISK_OR_MAINTENANCE_GATE_FAILED"
            if personal_failure
            else "HISTORICAL_PSEUDO_LOCK_NOT_OPENED_AND_CLEAN_L3_NOT_AVAILABLE"
        ),
        "gates": gates,
        "diagnostics": {
            "p00_vs_rm_delta_cagr": comparison["delta_cagr"],
            "p00_vs_rm_bootstrap_60": ci[60],
            "p00_vs_rm_mean_equity_weight_absolute_difference": str(risk_match_difference),
            "positive_six_month_windows": positive_windows,
            "eligible_six_month_windows": len(passed_windows),
            "positive_six_month_window_fraction": str(positive_fraction),
            "required_robustness_profiles": list(required_robustness),
            "local_parameter_nonnegative_count": local_nonnegative_count,
        },
    }


def execute_once(preflight: Mapping[str, object]) -> dict[str, object]:
    started_at = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
    attempt = {
        "statement_type": "已观察事实",
        "experiment_id": "HD-ANCHOR-001",
        "attempt_version": "HD-STAGE8-FORMAL-L2-PRELOCK-ATTEMPT-1.0",
        "started_at": started_at,
        "timezone": "Asia/Shanghai",
        "authorization_path": relative_path(AUTHORIZATION_PATH),
        "authorization_sha256": sha256(AUTHORIZATION_PATH),
        "scope": "ONE_COMPLETE_RETROSPECTIVE_L2_BATCH_[2022-03-10,2025-09-10)",
        "registered_paths": 96,
        "maximum_attempts": 1,
        "historical_pseudo_lock_status": "NOT_OPENED_NOT_READ",
    }
    write_exclusive_json(ATTEMPT_PATH, attempt)
    OUTPUT_DIR.mkdir(parents=False, exist_ok=False)

    profiles: Sequence[ProfileSpec] = preflight["profiles"]
    sessions: Sequence[MarketSession] = preflight["sessions"]
    all_session_dates: Sequence[date] = preflight["all_session_dates"]
    pit_records: Sequence[PITDividendRecord] = preflight["pit_records"]
    actions: Sequence[CorporateAction] = preflight["actions"]
    windows: Sequence[Mapping[str, str]] = preflight["windows"]
    base_fee_schedule = preflight["fee_schedule"]
    tax_schedule = preflight["tax_schedule"]

    all_paths: dict[str, dict[str, dict[str, object]]] = {}
    profile_results: dict[str, dict[str, object]] = {}
    daily_rows: list[dict[str, object]] = []
    signal_rows: list[dict[str, object]] = []
    outcome_rows: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    output_paths = [relative_path(OUTPUT_DIR / name) for name in OUTPUT_RELATIVE_NAMES]
    protocol_hash = sha256(EXPERIMENT / "method_freeze_manifest_v1.5.json")
    implementation_hash = sha256(BATCH_IMPLEMENTATION_MANIFEST_PATH)
    dataset_hash = sha256(DATASETS / "cleaned" / "data_manifest_v1_1_akshare_and_fee_v2.json")

    for profile in profiles:
        if not profile.runnable:
            paths = {}
            for account_id, _ in ACCOUNT_SPECS:
                ledger_rows.append({
                    "run_id": f"HD-STAGE8-L2-{profile.profile_id}-{account_id}",
                    "profile_id": profile.profile_id,
                    "account_id": account_id,
                    "hypothesis_id": "H1_VS_H0",
                    "dataset_hash": dataset_hash,
                    "protocol_hash": protocol_hash,
                    "implementation_hash": implementation_hash,
                    "seed": BOOTSTRAP_SEED,
                    "start_time": started_at,
                    "end_time": started_at,
                    "status": "NOT_RUN",
                    "failure_reason": profile.not_run_reason,
                    "all_output_paths": output_paths,
                    "locked_access_id": None,
                    "deviation_id": None,
                })
            profile_results[profile.profile_id] = {
                "status": "NOT_RUN",
                "reason": profile.not_run_reason,
                "paths": paths,
            }
            continue

        profile_sessions = tuple(item for item in sessions if item.session_date >= profile.start_date)
        if not profile_sessions or profile_sessions[0].session_date != profile.start_date:
            raise AssertionError(f"profile start is absent: {profile.profile_id}")
        fee_schedule = ScaledTransactionCostSchedule(
            base_fee_schedule, profile.fee_multiplier
        )
        selector = ProfilePITSelector(
            pit_records,
            session_dates=all_session_dates,
            available_delay_sessions=profile.pit_available_delay_sessions,
            dividend_multiplier=profile.dividend_multiplier,
        )
        strategy = ProfileStrategy(
            shifted_strategy_config(profile.yield_shift), profile.confirmation_bars
        )
        paths: dict[str, dict[str, object]] = {}
        for account_id, static_shares in ACCOUNT_SPECS:
            dynamic = account_id == "HD-ANCHOR-001"
            initial_shares = profile.dynamic_initial_shares if dynamic else int(static_shares)
            path_started = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
            path = run_path(
                profile=profile,
                account_id=account_id,
                initial_shares=initial_shares,
                profile_sessions=profile_sessions,
                selector=selector if dynamic else None,
                strategy=strategy if dynamic else None,
                fee_schedule=fee_schedule,
                tax_schedule=tax_schedule,
                actions=actions,
            )
            path_ended = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
            paths[account_id] = path
            daily_rows.extend(path["daily_rows"])
            if dynamic:
                signal_rows.extend(path["signal_rows"])
                outcome_rows.extend(path["outcome_rows"])
            ledger_rows.append({
                "run_id": f"HD-STAGE8-L2-{profile.profile_id}-{account_id}",
                "profile_id": profile.profile_id,
                "account_id": account_id,
                "hypothesis_id": "H1_VS_H0",
                "dataset_hash": dataset_hash,
                "protocol_hash": protocol_hash,
                "implementation_hash": implementation_hash,
                "seed": BOOTSTRAP_SEED,
                "start_time": path_started,
                "end_time": path_ended,
                "status": "COMPLETED",
                "failure_reason": None,
                "all_output_paths": output_paths,
                "locked_access_id": None,
                "deviation_id": None,
            })

        comparisons = profile_comparisons(paths)
        effects = {
            account_id: window_effects(
                paths["HD-ANCHOR-001"]["points"], paths[account_id]["points"], windows
            )
            for account_id in ("HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001")
        }
        profile_results[profile.profile_id] = {
            "status": "COMPLETED",
            "description": profile.description,
            "start_date": profile.start_date.isoformat(),
            "paths": {account_id: path["metrics"] for account_id, path in paths.items()},
            "comparisons": comparisons,
            "window_effects": effects,
        }
        all_paths[profile.profile_id] = paths

    if len(ledger_rows) != 96:
        raise AssertionError("run ledger does not contain exactly 96 registered paths")
    if sum(item["status"] == "COMPLETED" for item in ledger_rows) != 92:
        raise AssertionError("completed path count is not exactly 92")
    if sum(item["status"] == "NOT_RUN" for item in ledger_rows) != 4:
        raise AssertionError("P21 NOT_RUN path count is not exactly four")

    bootstrap_rows = bootstrap_intervals(all_paths)
    if len(bootstrap_rows) != 23 * 3 * 3:
        raise AssertionError("bootstrap output count is incomplete")
    p00_paths = all_paths["P00"]
    profile_results["P00"]["annual_relative_diagnostics_vs_rm"] = annual_relative_diagnostics(
        p00_paths["HD-ANCHOR-001"]["points"],
        p00_paths["HD-BASE-RM-001"]["points"],
    )
    evaluation = evaluate_batch(profile_results, bootstrap_rows, signal_rows)

    window_rows = [
        {
            "profile_id": profile_id,
            "comparator_id": comparator_id,
            **row,
        }
        for profile_id, profile in profile_results.items()
        if profile["status"] == "COMPLETED"
        for comparator_id, rows in profile["window_effects"].items()
        for row in rows
    ]

    write_parquet(OUTPUT_DIR / "daily_accounts.parquet", daily_rows)
    write_parquet(
        OUTPUT_DIR / "daily_close_signal_and_lagged_orders.parquet", signal_rows
    )
    write_parquet(
        OUTPUT_DIR / "auction_outcomes_daily_close_lagged.parquet", outcome_rows
    )
    write_exclusive_json(OUTPUT_DIR / "run_ledger.json", ledger_rows)
    write_exclusive_json(OUTPUT_DIR / "profile_results.json", profile_results)
    write_exclusive_json(OUTPUT_DIR / "window_results.json", window_rows)
    write_exclusive_json(OUTPUT_DIR / "bootstrap_intervals.json", bootstrap_rows)

    completed_at = datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
    result = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE8-FORMAL-L2-1.0-PRELOCK",
        "started_at": started_at,
        "completed_at": completed_at,
        "timezone": "Asia/Shanghai",
        "status": "COMPLETED_RETROSPECTIVE_L2_PRELOCK",
        "authorized_scope": {
            "start_inclusive": START.isoformat(),
            "end_exclusive": END.isoformat(),
            "session_observations": len(sessions),
            "trading_sessions": sum(item.trade_status == "TRADING" for item in sessions),
            "suspended_or_missing_sessions": sum(
                item.trade_status == "SUSPENDED_OR_MISSING" for item in sessions
            ),
            "retrospective_windows": [item["id"] for item in windows],
            "registered_profiles": 24,
            "registered_paths": 96,
            "completed_paths": 92,
            "not_run_paths": 4,
        },
        "primary_result": {
            "p00_dynamic": profile_results["P00"]["paths"]["HD-ANCHOR-001"],
            "risk_matched_static": profile_results["P00"]["paths"]["HD-BASE-RM-001"],
            "p00_vs_risk_matched": profile_results["P00"]["comparisons"]["HD-BASE-RM-001"],
            "bootstrap": [
                item for item in bootstrap_rows
                if item["profile_id"] == "P00"
                and item["comparator_id"] == "HD-BASE-RM-001"
            ],
        },
        "evaluation": evaluation,
        "integrity": {
            "input_hash_checks": preflight["hash_checks"],
            "daily_account_rows": len(daily_rows),
            "daily_signal_rows": len(signal_rows),
            "auction_outcome_rows": len(outcome_rows),
            "run_ledger_rows": len(ledger_rows),
            "profile_result_rows": len(profile_results),
            "window_result_rows": len(window_rows),
            "bootstrap_interval_rows": len(bootstrap_rows),
            "maximum_reconciliation_tolerance_cny": str(RECONCILIATION_TOLERANCE),
        },
        "bootstrap_method": {
            "method": "PAIRED_STATIONARY_BOOTSTRAP",
            "replications": BOOTSTRAP_REPLICATIONS,
            "seed": BOOTSTRAP_SEED,
            "expected_block_lengths_sessions": list(BOOTSTRAP_BLOCK_LENGTHS),
            "algorithm": "FIRST_UNIFORM_THEN_RESTART_WITH_PROBABILITY_1_OVER_L_ELSE_NEXT_MOD_N",
            "paired_indices_shared_across_dynamic_and_all_baselines": True,
            "quantile_method": "linear_empirical_0.025_0.975",
            "sampled_distributions_serialized": False,
        },
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "input_bindings": {
            "authorization": {
                "path": relative_path(AUTHORIZATION_PATH),
                "sha256": sha256(AUTHORIZATION_PATH),
            },
            "batch_implementation_manifest": {
                "path": relative_path(BATCH_IMPLEMENTATION_MANIFEST_PATH),
                "sha256": sha256(BATCH_IMPLEMENTATION_MANIFEST_PATH),
            },
            "exposure_calibration": {
                "path": relative_path(CALIBRATION_RESULT_PATH),
                "sha256": sha256(CALIBRATION_RESULT_PATH),
                "q_RM": RISK_MATCHED_SHARES,
            },
        },
        "outputs": output_paths,
        "authorization_and_counters": {
            "completed_formal_backtest_was_authorized": True,
            "formal_backtest_run_count": 1,
            "performance_calculation_count": 1,
            "exposure_calibration_run_count": 1,
            "historical_pseudo_lock_open_count": 0,
            "prospective_lock_open_count": 0,
            "paper_trading_authorized": False,
            "live_trading_authorized": False,
            "dry_run": True,
        },
        "locked_period_status": "NOT_OPENED_NOT_READ",
        "evidence_ceiling": "L2_RETROSPECTIVE",
        "research_decision": evaluation["decision"],
    }
    write_exclusive_json(RESULT_PATH, result)
    return result


def record_failure(exc: BaseException) -> None:
    if FAILURE_PATH.exists():
        return
    payload = {
        "statement_type": "已观察事实",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE8-FORMAL-L2-FAILURE-1.0-PRELOCK",
        "failed_at": datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds"),
        "status": "FAILED_ONE_SHOT_ATTEMPT_REQUIRES_NEW_AUTHORIZATION_FOR_ANY_RERUN",
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc(),
        "historical_pseudo_lock_status": "NOT_OPENED_NOT_READ",
        "formal_backtest_attempt_count": 1,
    }
    write_exclusive_json(FAILURE_PATH, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-authorized-once", action="store_true")
    args = parser.parse_args()

    preflight = load_and_preflight()
    if args.preflight:
        print(json.dumps({
            "status": "PASS_READY_FOR_ONE_AUTHORIZED_FORMAL_L2_PRELOCK_BATCH",
            "authorized_window": "[2022-03-10, 2025-09-10)",
            "session_observations": len(preflight["sessions"]),
            "trading_sessions": sum(
                item.trade_status == "TRADING" for item in preflight["sessions"]
            ),
            "registered_profiles": len(preflight["profiles"]),
            "registered_paths": len(preflight["profiles"]) * len(ACCOUNT_SPECS),
            "P21_status": "NOT_RUN",
            "historical_pseudo_lock_status": "NOT_OPENED_NOT_READ",
            "hash_checks": preflight["hash_checks"],
        }, ensure_ascii=False, indent=2))
        return 0

    try:
        result = execute_once(preflight)
    except BaseException as exc:
        record_failure(exc)
        raise
    print(json.dumps({
        "status": result["status"],
        "research_decision": result["research_decision"],
        "evidence_ceiling": result["evidence_ceiling"],
        "locked_period_status": result["locked_period_status"],
        "primary_result": result["primary_result"]["p00_vs_risk_matched"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
