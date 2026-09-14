"""Independent one-time validation of the Stage 8 formal L2 reproduction."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
ORIGINAL_OUTPUT = EXPERIMENT / "formal_l2_v1.0_prelock"
REPRO_OUTPUT = EXPERIMENT / "formal_l2_reproduction_v1.0"
ORIGINAL_RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
REPRO_RESULT = EXPERIMENT / "formal_l2_reproduction_result_v1.0.json"
RAW_RESULT = EXPERIMENT / "formal_l2_reproduction_raw_result_v1.0.json"
ATTEMPT = EXPERIMENT / "formal_l2_reproduction_attempt_v1.0.json"
PLAN = EXPERIMENT / "formal_l2_reproduction_plan_v1.0_pre_results.json"
AUTHORIZATION = EXPERIMENT / "FORMAL_L2_REPRODUCTION_AUTHORIZATION_2026-09-14.json"
FAILURE = EXPERIMENT / "formal_l2_reproduction_failure_v1.0.json"
VALIDATION = EXPERIMENT / "formal_l2_reproduction_validation_v1.0.json"
TOLERANCE = Decimal("0.01")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_exclusive_json(path: Path, payload: object) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def normalized_ledger(path: Path) -> list[dict]:
    return [
        {
            key: value
            for key, value in row.items()
            if key not in {"start_time", "end_time", "all_output_paths"}
        }
        for row in load_json(path)
    ]


def main() -> int:
    if VALIDATION.exists():
        raise AssertionError("reproduction validation already exists")
    if FAILURE.exists():
        raise AssertionError("reproduction failure artifact exists")

    plan = load_json(PLAN)
    authorization = load_json(AUTHORIZATION)
    result = load_json(REPRO_RESULT)
    raw_result = load_json(RAW_RESULT)
    original_result = load_json(ORIGINAL_RESULT)
    attempt = load_json(ATTEMPT)

    assert plan["artifact_version"] == "HD-STAGE8-FORMAL-L2-REPRODUCTION-PLAN-1.0-PRE-RESULTS"
    assert authorization["status"] == "AUTHORIZED_ONE_VERSIONED_FORMAL_L2_REPRODUCTION"
    assert authorization["authorization_context"]["researcher_reply"] == "授权"
    assert authorization["interval"] == "[2022-03-10, 2025-09-10)"
    assert authorization["registered_paths"] == 96
    assert authorization["q_RM"] == 900
    assert authorization["historical_pseudo_lock_open_authorized"] is False
    assert result["status"] == "PASS_EXACT_VALUE_REPRODUCTION"
    assert result["comparison_to_original_frozen_batch"]["all_registered_numeric_and_state_outputs_equal"] is True
    assert attempt["maximum_attempts"] == 1

    counters = result["authorization_and_counters"]
    assert counters["formal_backtest_run_count"] == 2
    assert counters["performance_calculation_count"] == 2
    assert counters["formal_l2_reproduction_run_count"] == 1
    assert counters["historical_pseudo_lock_open_count"] == 0
    assert counters["prospective_lock_open_count"] == 0
    assert counters["dry_run"] is True

    json_names = ("profile_results.json", "window_results.json", "bootstrap_intervals.json")
    for name in json_names:
        assert load_json(REPRO_OUTPUT / name) == load_json(ORIGINAL_OUTPUT / name), name

    parquet_names = (
        "daily_accounts.parquet",
        "daily_close_signal_and_lagged_orders.parquet",
        "auction_outcomes_daily_close_lagged.parquet",
    )
    parquet_hashes_equal: dict[str, bool] = {}
    for name in parquet_names:
        original_path = ORIGINAL_OUTPUT / name
        reproduction_path = REPRO_OUTPUT / name
        assert pq.read_table(reproduction_path).equals(pq.read_table(original_path)), name
        parquet_hashes_equal[name] = sha256(reproduction_path) == sha256(original_path)
        assert parquet_hashes_equal[name], name

    assert normalized_ledger(REPRO_OUTPUT / "run_ledger.json") == normalized_ledger(
        ORIGINAL_OUTPUT / "run_ledger.json"
    )
    ledger = load_json(REPRO_OUTPUT / "run_ledger.json")
    assert len(ledger) == 96
    assert sum(row["status"] == "COMPLETED" for row in ledger) == 92
    assert sum(row["status"] == "NOT_RUN" for row in ledger) == 4
    assert {row["profile_id"] for row in ledger if row["status"] == "NOT_RUN"} == {"P21"}

    for field in (
        "primary_result",
        "evaluation",
        "integrity",
        "bootstrap_method",
        "runtime",
        "locked_period_status",
        "evidence_ceiling",
        "research_decision",
    ):
        assert raw_result[field] == original_result[field], field

    daily = pq.read_table(
        REPRO_OUTPUT / "daily_accounts.parquet",
        columns=[
            "profile_id",
            "account_id",
            "session_date",
            "nav_cny",
            "reconciliation_difference_cny",
        ],
    )
    assert daily.num_rows == 77640
    assert max(
        abs(Decimal(value)) for value in daily["reconciliation_difference_cny"].to_pylist()
    ) <= TOLERANCE
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

    output_hashes = [
        {
            "path": relative(path),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in (
            PLAN,
            AUTHORIZATION,
            ATTEMPT,
            RAW_RESULT,
            REPRO_RESULT,
            *sorted(REPRO_OUTPUT.iterdir(), key=lambda item: item.name),
        )
        if path.is_file()
    ]
    payload = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE8-FORMAL-L2-REPRODUCTION-VALIDATION-1.0",
        "status": "PASS_INDEPENDENT_EXACT_VALUE_REPRODUCTION_VALIDATION",
        "checks_passed": 34,
        "registered_paths": 96,
        "completed_paths": 92,
        "not_run_paths": 4,
        "daily_account_rows": 77640,
        "p00_session_observations": 852,
        "maximum_authorized_date": "2025-09-09",
        "all_json_values_equal": True,
        "all_parquet_table_values_equal": True,
        "all_parquet_file_hashes_equal": all(parquet_hashes_equal.values()),
        "normalized_run_ledger_equal": True,
        "raw_result_fields_equal": True,
        "daily_reconciliation": "PASS_ALL_COMPLETED_PATHS_WITHIN_CNY_0.01",
        "p00_initial_nav_cny": "60000.0000",
        "p00_final_nav_cny": "70119.1800",
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "formal_backtest_run_count": 2,
        "performance_calculation_count": 2,
        "evidence_ceiling": "L2_RETROSPECTIVE",
        "output_hashes": output_hashes,
    }
    write_exclusive_json(VALIDATION, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
