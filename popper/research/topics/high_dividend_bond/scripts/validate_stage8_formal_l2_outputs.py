"""Read-only integrity checks for the frozen Stage 8 formal L2 prelock batch."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq


TOPIC_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
OUTPUT = EXPERIMENT / "formal_l2_v1.0_prelock"
RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
ATTEMPT = EXPERIMENT / "formal_l2_attempt_v1.0_prelock.json"
FAILURE = EXPERIMENT / "formal_l2_failure_v1.0_prelock.json"
END = date(2025, 9, 10)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def parquet_dates_before_end(path: Path, column: str = "session_date") -> bool:
    table = pq.read_table(path, columns=[column])
    values = [value for value in table[column].to_pylist() if value is not None]
    return bool(values) and max(date.fromisoformat(value) for value in values) < END


def main() -> int:
    result = load_json(RESULT)
    attempt = load_json(ATTEMPT)
    ledger = load_json(OUTPUT / "run_ledger.json")
    profiles = load_json(OUTPUT / "profile_results.json")
    windows = load_json(OUTPUT / "window_results.json")
    bootstrap = load_json(OUTPUT / "bootstrap_intervals.json")

    assert not FAILURE.exists(), "successful batch must not have a failure record"
    assert attempt["maximum_attempts"] == 1
    assert result["status"] == "COMPLETED_RETROSPECTIVE_L2_PRELOCK"
    assert result["research_decision"] in {"接受", "观察", "修改", "淘汰"}
    assert result["research_decision"] == "修改"
    assert result["locked_period_status"] == "NOT_OPENED_NOT_READ"
    assert result["authorization_and_counters"]["formal_backtest_run_count"] == 1
    assert result["authorization_and_counters"]["performance_calculation_count"] == 1
    assert result["authorization_and_counters"]["historical_pseudo_lock_open_count"] == 0

    assert len(ledger) == 96
    assert sum(row["status"] == "COMPLETED" for row in ledger) == 92
    assert sum(row["status"] == "NOT_RUN" for row in ledger) == 4
    assert {
        row["profile_id"] for row in ledger if row["status"] == "NOT_RUN"
    } == {"P21"}
    assert {row["failure_reason"] for row in ledger if row["status"] == "NOT_RUN"} == {
        "NO_AUDITABLE_EXECUTABLE_BROKER_CASH_RATE_INPUT"
    }
    assert len(profiles) == 24 and profiles["P21"]["status"] == "NOT_RUN"
    assert len(windows) == 483
    assert not any(str(row["window_id"]).startswith("PLOCK") for row in windows)
    assert len(bootstrap) == 207
    assert {row["expected_block_length_sessions"] for row in bootstrap} == {20, 60, 120}
    assert {row["replications"] for row in bootstrap} == {5000}
    assert {row["seed"] for row in bootstrap} == {20260905}

    expected_parquet = {
        "daily_accounts.parquet": (77640, 27),
        "daily_close_signal_and_lagged_orders.parquet": (19410, 17),
        "auction_outcomes_daily_close_lagged.parquet": (214, 18),
    }
    for name, (rows, columns) in expected_parquet.items():
        metadata = pq.ParquetFile(OUTPUT / name).metadata
        assert (metadata.num_rows, metadata.num_columns) == (rows, columns)
        assert parquet_dates_before_end(OUTPUT / name)

    daily = pq.read_table(
        OUTPUT / "daily_accounts.parquet",
        columns=[
            "profile_id", "account_id", "session_date", "nav_cny",
            "reconciliation_difference_cny",
        ],
    )
    p00 = daily.filter(
        pc.and_(
            pc.equal(daily["profile_id"], "P00"),
            pc.equal(daily["account_id"], "HD-ANCHOR-001"),
        )
    )
    assert p00.num_rows == 852
    assert p00["session_date"][0].as_py() == "2022-03-10"
    assert p00["session_date"][-1].as_py() == "2025-09-09"
    assert Decimal(p00["nav_cny"][0].as_py()) == Decimal("60000.0000")
    assert Decimal(p00["nav_cny"][-1].as_py()) == Decimal("70119.1800")
    assert max(
        abs(Decimal(value)) for value in daily["reconciliation_difference_cny"].to_pylist()
    ) <= Decimal("0.01")

    printed = {
        "status": "PASS_FROZEN_FORMAL_L2_OUTPUT_INTEGRITY",
        "registered_paths": len(ledger),
        "completed_paths": 92,
        "not_run_paths": 4,
        "daily_account_rows": daily.num_rows,
        "window_rows": len(windows),
        "bootstrap_interval_rows": len(bootstrap),
        "maximum_authorized_date": "2025-09-09",
        "historical_pseudo_lock_status": "NOT_OPENED_NOT_READ",
        "research_decision": result["research_decision"],
    }
    print(json.dumps(printed, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
