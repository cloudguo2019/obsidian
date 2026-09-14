"""Versioned deterministic reproduction of the frozen Stage 8 formal L2 batch.

Preflight is read-only and may run before authorization. Execution requires a
machine-readable exact-scope authorization and writes only new reproduction
paths. The original frozen producer and outputs are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"

PRODUCER = Path(__file__).with_name("run_stage8_formal_l2_batch.py")
PLAN = EXPERIMENT / "formal_l2_reproduction_plan_v1.0_pre_results.json"
AUTHORIZATION = EXPERIMENT / "FORMAL_L2_REPRODUCTION_AUTHORIZATION_2026-09-14.json"
ATTEMPT = EXPERIMENT / "formal_l2_reproduction_attempt_v1.0.json"
RAW_RESULT = EXPERIMENT / "formal_l2_reproduction_raw_result_v1.0.json"
RESULT = EXPERIMENT / "formal_l2_reproduction_result_v1.0.json"
FAILURE = EXPERIMENT / "formal_l2_reproduction_failure_v1.0.json"
OUTPUT = EXPERIMENT / "formal_l2_reproduction_v1.0"

ORIGINAL_RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
ORIGINAL_OUTPUT = EXPERIMENT / "formal_l2_v1.0_prelock"
EXPECTED_PRODUCER_SHA256 = "d078a902a11d00de1960699c007c8bbbac8fbf99de18e38fd9e2dba7350875ef"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_exclusive_json(path: Path, payload: Any) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def verify_environment() -> dict[str, str]:
    import akshare
    import pandas
    import pyarrow

    actual = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "akshare": akshare.__version__,
        "pandas": pandas.__version__,
        "pyarrow": pyarrow.__version__,
    }
    expected = {
        "python": "3.11.9",
        "implementation": "CPython",
        "akshare": "1.18.94",
        "pandas": "3.0.5",
        "pyarrow": "25.0.1",
    }
    if actual != expected:
        raise AssertionError(f"frozen environment mismatch: {actual}")
    return actual


def verify_plan_bindings() -> int:
    plan = load_json(PLAN)
    if plan["status"] != "READY_FOR_READ_ONLY_PREFLIGHT_PENDING_EXACT_EXECUTION_AUTHORIZATION":
        raise AssertionError("unexpected reproduction plan status")
    checked = 0
    for item in plan["bindings"]:
        path = REPO_ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise AssertionError(f"reproduction plan binding changed: {item['path']}")
        checked += 1
    return checked


def load_producer():
    if sha256(PRODUCER) != EXPECTED_PRODUCER_SHA256:
        raise AssertionError("frozen Stage 8 producer hash changed")
    spec = importlib.util.spec_from_file_location("hd_stage8_frozen_producer", PRODUCER)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load frozen Stage 8 producer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configure_producer(module, authorization_path: Path) -> None:
    module.AUTHORIZATION_PATH = authorization_path
    module.ATTEMPT_PATH = ATTEMPT
    module.RESULT_PATH = RAW_RESULT
    module.FAILURE_PATH = FAILURE
    module.OUTPUT_DIR = OUTPUT


def assert_new_paths_absent() -> None:
    existing = [path for path in (ATTEMPT, RAW_RESULT, RESULT, FAILURE, OUTPUT) if path.exists()]
    if existing:
        raise AssertionError(
            "versioned reproduction path already exists: " + ", ".join(relative(path) for path in existing)
        )


def verify_authorization() -> dict[str, Any]:
    if not AUTHORIZATION.is_file():
        raise AssertionError("exact-scope reproduction authorization is missing")
    authorization = load_json(AUTHORIZATION)
    required = {
        "status": "AUTHORIZED_ONE_VERSIONED_FORMAL_L2_REPRODUCTION",
        "interval": "[2022-03-10, 2025-09-10)",
        "profiles": "P00-P23_ALL_24_REGISTERED_PROFILES",
        "registered_paths": 96,
        "q_RM": 900,
        "historical_pseudo_lock_open_authorized": False,
        "prospective_lock_open_authorized": False,
        "paper_trading_authorized": False,
        "live_trading_authorized": False,
        "dry_run": True,
    }
    for key, expected in required.items():
        if authorization.get(key) != expected:
            raise AssertionError(f"authorization field mismatch: {key}")
    return authorization


def normalized_ledger(path: Path) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in load_json(path):
        normalized.append({
            key: value
            for key, value in row.items()
            if key not in {"start_time", "end_time", "all_output_paths"}
        })
    return normalized


def compare_outputs(raw_result: dict[str, Any]) -> dict[str, Any]:
    import pyarrow.parquet as pq

    json_names = ("profile_results.json", "window_results.json", "bootstrap_intervals.json")
    json_equal = {
        name: load_json(OUTPUT / name) == load_json(ORIGINAL_OUTPUT / name)
        for name in json_names
    }
    parquet_names = (
        "daily_accounts.parquet",
        "daily_close_signal_and_lagged_orders.parquet",
        "auction_outcomes_daily_close_lagged.parquet",
    )
    parquet_table_equal = {
        name: pq.read_table(OUTPUT / name).equals(pq.read_table(ORIGINAL_OUTPUT / name))
        for name in parquet_names
    }
    parquet_file_hash_equal = {
        name: sha256(OUTPUT / name) == sha256(ORIGINAL_OUTPUT / name)
        for name in parquet_names
    }
    ledger_equal = normalized_ledger(OUTPUT / "run_ledger.json") == normalized_ledger(
        ORIGINAL_OUTPUT / "run_ledger.json"
    )
    original_result = load_json(ORIGINAL_RESULT)
    result_fields = (
        "primary_result",
        "evaluation",
        "integrity",
        "bootstrap_method",
        "runtime",
        "locked_period_status",
        "evidence_ceiling",
        "research_decision",
    )
    result_field_equal = {
        field: raw_result[field] == original_result[field]
        for field in result_fields
    }
    all_equal = (
        all(json_equal.values())
        and all(parquet_table_equal.values())
        and ledger_equal
        and all(result_field_equal.values())
    )
    return {
        "all_registered_numeric_and_state_outputs_equal": all_equal,
        "json_value_equal": json_equal,
        "parquet_table_value_equal": parquet_table_equal,
        "parquet_file_hash_equal": parquet_file_hash_equal,
        "run_ledger_equal_after_removing_run_times_and_output_paths": ledger_equal,
        "raw_result_field_equal": result_field_equal,
    }


def output_hashes() -> list[dict[str, Any]]:
    paths = [ATTEMPT, RAW_RESULT, *sorted(OUTPUT.iterdir(), key=lambda path: path.name)]
    return [
        {"path": relative(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}
        for path in paths
        if path.is_file()
    ]


def run_preflight() -> dict[str, Any]:
    assert_new_paths_absent()
    environment = verify_environment()
    plan_bindings = verify_plan_bindings()
    module = load_producer()
    configure_producer(module, PLAN)
    preflight = module.load_and_preflight()
    return {
        "status": "PASS_READY_PENDING_EXACT_REPRODUCTION_AUTHORIZATION",
        "environment": environment,
        "plan_bindings_checked": plan_bindings,
        "authorized_interval_if_confirmed": "[2022-03-10, 2025-09-10)",
        "session_observations": len(preflight["sessions"]),
        "trading_sessions": sum(
            item.trade_status == "TRADING" for item in preflight["sessions"]
        ),
        "registered_profiles": len(preflight["profiles"]),
        "registered_paths": len(preflight["profiles"]) * len(module.ACCOUNT_SPECS),
        "P21_status": "NOT_RUN",
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "execution_authorized": False,
    }


def execute_authorized_once() -> dict[str, Any]:
    assert_new_paths_absent()
    environment = verify_environment()
    plan_bindings = verify_plan_bindings()
    authorization = verify_authorization()
    module = load_producer()
    configure_producer(module, AUTHORIZATION)
    preflight = module.load_and_preflight()
    raw_result = module.execute_once(preflight)
    comparison = compare_outputs(raw_result)
    payload = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE8-FORMAL-L2-REPRODUCTION-RESULT-1.0",
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "status": (
            "PASS_EXACT_VALUE_REPRODUCTION"
            if comparison["all_registered_numeric_and_state_outputs_equal"]
            else "FAIL_REPRODUCTION_MISMATCH"
        ),
        "authorized_scope": authorization,
        "environment": environment,
        "plan_bindings_checked": plan_bindings,
        "comparison_to_original_frozen_batch": comparison,
        "raw_producer_result_path": relative(RAW_RESULT),
        "raw_producer_result_sha256": sha256(RAW_RESULT),
        "output_hashes": output_hashes(),
        "authorization_and_counters": {
            "formal_backtest_run_count": 2,
            "performance_calculation_count": 2,
            "exposure_calibration_run_count": 1,
            "formal_l2_reproduction_run_count": 1,
            "historical_pseudo_lock_open_count": 0,
            "prospective_lock_open_count": 0,
            "paper_trading_authorized": False,
            "live_trading_authorized": False,
            "dry_run": True
        },
        "evidence_effect": "NO_UPGRADE_SAME_RETROSPECTIVE_SAMPLE",
        "evidence_ceiling": "L2_RETROSPECTIVE",
        "research_decision_effect": "REPRODUCTION_ONLY_NO_AUTOMATIC_CHANGE"
    }
    write_exclusive_json(RESULT, payload)
    if payload["status"] != "PASS_EXACT_VALUE_REPRODUCTION":
        raise AssertionError("versioned formal L2 reproduction differs from frozen original")
    return payload


def record_wrapper_failure(exc: BaseException) -> None:
    if FAILURE.exists():
        return
    write_exclusive_json(FAILURE, {
        "statement_type": "已观察事实",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE8-FORMAL-L2-REPRODUCTION-FAILURE-1.0",
        "failed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "FAILED_VERSIONED_REPRODUCTION_REQUIRES_NEW_AUTHORIZATION_FOR_RETRY",
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc(),
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ"
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute-authorized-once", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(run_preflight(), ensure_ascii=False, indent=2))
        return 0
    try:
        result = execute_authorized_once()
    except BaseException as exc:
        record_wrapper_failure(exc)
        raise
    print(json.dumps({
        "status": result["status"],
        "comparison": result["comparison_to_original_frozen_batch"],
        "authorization_and_counters": result["authorization_and_counters"],
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ"
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
