"""Refine the frozen audit without changing sample selection or old outputs."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import timedelta
from pathlib import Path

from audit_phase1_readonly_v1 import ROOT, TOPIC, DATA, ENGINE, digest, records, timestamp

BASE = TOPIC / "datasets/PHASE1_READONLY_AUDIT_v1.0_2026-09-16.json"


def refine():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    for item in base["inputs"]:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError("Input identity changed: " + item["path"])
    execution = Counter()
    age_samples = []
    for day in base["selection"]["dates"]:
        path = DATA / "logs/simulate" / day / "etf_closing_auction.csv"
        for row in records(path):
            if row["stage"] != "proxy_close_captured":
                continue
            event, quote = timestamp(row["event_time"]), timestamp(row["quote_time"])
            if event is None or quote is None:
                execution["invalid_time"] += 1
                continue
            age = (event - quote).total_seconds()
            age_samples.append(age)
            execution["rows"] += 1
            execution["quote_later_than_logged_event"] += age < 0
            # Logger truncates event_time to whole seconds. A quote at least
            # one second later cannot be explained by that truncation alone.
            execution["quote_at_least_1s_later_than_logged_event"] += age <= -1
            execution["subsecond_order_ambiguous"] += -1 < age < 0
    ticks = {"before_1500": Counter(), "at_or_after_1500": Counter()}
    cases = []
    for day in base["selection"]["dates"]:
        for symbol in base["selection"]["tick_symbols"]:
            path = DATA / "data/market_tick/csv" / day.replace("-", "") / (symbol + ".csv")
            rows = records(path)
            before = Counter()
            statuses = Counter()
            ages = []
            for row in rows:
                received, quote = timestamp(row["captured_at"]), timestamp(row["quote_time"])
                if received is None or quote is None:
                    raise RuntimeError("Selected tick timestamps unexpectedly invalid")
                label = "before_1500" if received.time().isoformat() < "15:00:00" else "at_or_after_1500"
                counts = ticks[label]
                counts["rows"] += 1
                counts["flagged_stale"] += row["is_stale"].lower() == "true"
                counts["quote_after_host_capture"] += quote > received
                counts["quote_more_than_1s_after_host_capture"] += quote > received + timedelta(seconds=1)
                if label == "before_1500":
                    before.update({"rows": 1, "quote_after_host_capture": int(quote > received), "flagged_stale": int(row["is_stale"].lower() == "true")})
                    statuses[row["stock_status"]] += 1
                    ages.append((received - quote).total_seconds())
            cases.append({"date": day, "symbol": symbol, "before_1500": dict(before), "before_1500_statuses": dict(statuses), "before_1500_quote_age_seconds_min_max": [min(ages), max(ages)] if ages else None})
    tick_dirs = sorted(p for p in (DATA / "data/market_tick/csv").iterdir() if p.is_dir())
    inventory = [{"date_directory": p.name, "csv_count": len(list(p.glob("*.csv")))} for p in tick_dirs]
    logger_path = ENGINE / "sartre_core/engine/runtime_logger.py"
    assert "event_time.isoformat(timespec=\"seconds\")" in logger_path.read_text(encoding="utf-8")
    return {
        "identity": "ETF-PHASE1-TIMESTAMP-AMENDMENT-20260916-v1.0",
        "parent_audit": BASE.relative_to(ROOT).as_posix(), "parent_sha256": digest(BASE),
        "script_sha256": digest(Path(__file__)), "logger_sha256": digest(logger_path),
        "sample_selection_unchanged": base["selection"],
        "input_hashes_revalidated": len(base["inputs"]),
        "execution_event_vs_quote": dict(execution),
        "execution_logged_age_seconds_min_max": [min(age_samples), max(age_samples)],
        "tick_capture_vs_quote_by_window": {k: dict(v) for k, v in ticks.items()},
        "tick_before_1500_cases": cases,
        "tick_filename_inventory": inventory,
        "interpretation": [
            "Negative host-receipt minus vendor-quote age demonstrates timestamp incompatibility, not access to future market information or intentional lookahead.",
            "At least one second of quote lead cannot be explained solely by truncating event_time to whole seconds; clock skew, polling duration and vendor timestamps require validation.",
            "Pipeline captures now once before sequential per-symbol polling; event_time is not each quote's exact receipt time.",
            "captured_at records the polling observation time, not an SDK exchange receive acknowledgement.",
            "Stale flags over the 14:57-15:30 capture session include post-close repeats; use the before-15:00 subset to assess executable-window quality.",
            "The 23-date filename inventory is not a full content audit; only the predetermined 24 tick files were inspected.",
        ],
        "evidence_ceiling": "L0", "formal_backtests": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(TOPIC):
        raise SystemExit("Output must be a new versioned ETF artifact")
    result = refine()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.as_posix(), "execution": result["execution_event_vs_quote"], "ticks": result["tick_capture_vs_quote_by_window"], "tick_date_inventory_count": len(result["tick_filename_inventory"])}, ensure_ascii=False))
