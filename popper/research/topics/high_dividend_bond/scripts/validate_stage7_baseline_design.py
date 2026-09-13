"""Validate the frozen stage-7 baseline design without running a strategy.

The validator reads only frozen manifests, corporate-action dates, and the
unadjusted close at pre-registered initialization dates.  It never generates
signals, positions, returns, NAV, drawdowns, or benchmark performance.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_price_rows(path: Path) -> tuple[dict[date, dict[str, str]], list[date]]:
    rows: dict[date, dict[str, str]] = {}
    trading_sessions: list[date] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"session_date", "close", "trade_status"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"cleaned price missing fields: {sorted(missing)}")
        for row in reader:
            session = date.fromisoformat(row["session_date"])
            rows[session] = row
            if row["trade_status"] == "TRADING":
                trading_sessions.append(session)
    return rows, sorted(trading_sessions)


def first_session_on_or_after(sessions: list[date], anchor: date) -> date:
    for session in sessions:
        if session >= anchor:
            return session
    raise ValueError(f"no trading session on or after {anchor.isoformat()}")


def cross_period_entitlements(path: Path, starts: list[date]) -> dict[str, list[str]]:
    result = {start.isoformat(): [] for start in starts}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"action_id", "record_date", "pay_date"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"corporate actions missing fields: {sorted(missing)}")
        for row in reader:
            record_date = date.fromisoformat(row["record_date"])
            pay_date = date.fromisoformat(row["pay_date"])
            for start in starts:
                if record_date < start <= pay_date:
                    result[start.isoformat()].append(row["action_id"])
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    experiment_dir = root / "research/topics/high_dividend_bond/experiments/HD-ANCHOR-001"
    design_path = experiment_dir / "baseline_design_v1.0_frozen.json"
    design = read_json(design_path)

    checked_hashes: dict[str, str] = {}
    for item in design["inputs"]:  # type: ignore[index]
        rel_path = item["path"]
        actual = sha256(root / rel_path)
        if actual != item["sha256"]:
            raise ValueError(f"hash mismatch: {rel_path}")
        checked_hashes[rel_path] = actual

    price_rel = "research/topics/high_dividend_bond/datasets/cleaned/cleaned_price.csv"
    actions_rel = "research/topics/high_dividend_bond/datasets/cleaned/corporate_actions.csv"
    price_rows, trading_sessions = read_price_rows(root / price_rel)

    expected_dates = {
        "calibration": date(2019, 3, 11),
        "P00": date(2022, 3, 10),
        "P08": date(2022, 6, 10),
        "P09": date(2022, 9, 13),
    }
    anchors = {
        "calibration": date(2019, 3, 10),
        "P00": date(2022, 3, 10),
        "P08": date(2022, 6, 10),
        "P09": date(2022, 9, 10),
    }
    observed_prices: dict[str, float] = {}
    for profile, expected in expected_dates.items():
        resolved = first_session_on_or_after(trading_sessions, anchors[profile])
        if resolved != expected:
            raise ValueError(f"unexpected resolved date for {profile}: {resolved}")
        row = price_rows[resolved]
        if row["trade_status"] != "TRADING":
            raise ValueError(f"initialization date not tradable: {resolved}")
        observed_prices[profile] = float(row["close"])

    initialization = design["initialization"]  # type: ignore[index]
    main_price = observed_prices["P00"]
    if main_price != initialization["main_oos_price_ref_cny"]:
        raise ValueError("main OOS reference price mismatch")
    buffered_raw = 1.10 * 1500 * main_price
    rounded_requirement = math.ceil(buffered_raw / 1000) * 1000
    if rounded_requirement != initialization["rounded_buffer_requirement_cny"]:
        raise ValueError("rounded funding requirement mismatch")
    if max(60000, rounded_requirement) != initialization["common_initial_assets_cny"]:
        raise ValueError("common initial assets mismatch")

    starts = list(expected_dates.values())
    entitlements = cross_period_entitlements(root / actions_rel, starts)
    if any(entitlements.values()):
        raise ValueError(f"cross-period entitlements require explicit initialization: {entitlements}")

    calibration_start = expected_dates["calibration"]
    calibration_end = expected_dates["P00"]
    calibration_rows = [
        row
        for session, row in price_rows.items()
        if calibration_start <= session < calibration_end
    ]
    calibration_trading = sum(row["trade_status"] == "TRADING" for row in calibration_rows)
    derivation = design["risk_matching_derivation"]  # type: ignore[index]
    if len(calibration_rows) != derivation["calibration_calendar_sessions"]:
        raise ValueError("calibration calendar-session count mismatch")
    if calibration_trading != derivation["calibration_trading_sessions"]:
        raise ValueError("calibration trading-session count mismatch")

    result = {
        "statement_type": "计算结果",
        "validator_version": "HD-STAGE7-BASELINE-VALIDATOR-1.0.0",
        "status": "PASS",
        "design_sha256": sha256(design_path),
        "checked_input_hashes": checked_hashes,
        "resolved_initialization_prices_cny": observed_prices,
        "buffered_raw_requirement_cny": round(buffered_raw, 2),
        "rounded_buffer_requirement_cny": rounded_requirement,
        "common_initial_assets_cny": initialization["common_initial_assets_cny"],
        "cross_period_entitlements": entitlements,
        "calibration_calendar_sessions": len(calibration_rows),
        "calibration_trading_sessions": calibration_trading,
        "calibration_suspended_or_missing_sessions": len(calibration_rows) - calibration_trading,
        "fields_read_from_price": ["session_date", "close", "trade_status"],
        "strategy_run_count": 0,
        "performance_calculation_count": 0,
        "historical_pseudo_lock_open_count": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
