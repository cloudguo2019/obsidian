"""Bounded, read-only phase-1 audit. Never connects to QMT or computes performance."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOPIC = ROOT / "research/topics/etf_rotation_macd"
DATA = ROOT / "research/QMTData"
ENGINE = ROOT.parents[1] / "FINITUDE-1.4.2/sartre"
TZ = timezone(timedelta(hours=8))
PLAN = TOPIC / "datasets/PHASE1_READONLY_PLAN_v1.0_2026-09-16.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def records(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        return result.replace(tzinfo=TZ) if result.tzinfo is None else result.astimezone(TZ)
    except (TypeError, ValueError):
        return None


def position_map_size(value):
    for loader in (json.loads, ast.literal_eval):
        try:
            parsed = loader(value)
            if isinstance(parsed, dict):
                return str(len(parsed))
        except (ValueError, SyntaxError, TypeError):
            pass
    return "unparseable"


def audit():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    inputs = [{"path": PLAN.relative_to(ROOT).as_posix(), "sha256": digest(PLAN)}]

    def read(path):
        inputs.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size})
        return records(path)

    pool = read(DATA / "data/etf_universe/interest_etf.csv")
    symbols = sorted({r["symbol"] for r in pool})
    chosen = sorted([s for s in symbols if s.endswith(".SH")][:2] + [s for s in symbols if s.endswith(".SZ")][:1])
    logs = []
    cases = []
    totals = Counter()
    for day in plan["dates"]:
        item = {"date": day, "files": {}, "tick_inventory_count": 0}
        for name in plan["log_files_per_date"]:
            path = DATA / "logs/simulate" / day / name
            if not path.exists():
                item["files"][name] = {"exists": False}
                continue
            rows = read(path)
            summary = {"exists": True, "rows": len(rows), "columns": list(rows[0]) if rows else []}
            if name == "etf_tick_capture.csv":
                captures = [r for r in rows if r["stage"] == "summary"]
                summary["summary_symbols"] = len({r["symbol"] for r in captures})
                summary["capture_counts"] = {k: sum(number(r.get(k)) or 0 for r in captures) for k in ["expected_count", "actual_count", "valid_count", "missing_count", "stale_count", "error_count", "invalid_count"]}
            elif name == "etf_closing_auction.csv":
                summary["stages"] = dict(Counter(r["stage"] for r in rows))
                summary["daily_outcomes"] = dict(Counter(r["outcome"] for r in rows if r["stage"] == "daily_summary"))
                captured = [r for r in rows if r["stage"] == "proxy_close_captured"]
                checks = Counter()
                ages = []
                for r in captured:
                    event = timestamp(r.get("event_time"))
                    quote = timestamp(r.get("quote_time"))
                    checks["captured_rows"] += 1
                    if event is None or quote is None:
                        checks["missing_or_invalid_timestamp"] += 1
                        continue
                    age = (event - quote).total_seconds()
                    ages.append(age)
                    checks["future_quote"] += age < 0
                    checks["quote_age_over_5s"] += age > 5
                    checks["quote_before_145730"] += quote.time().isoformat() < "14:57:30"
                    checks["event_outside_submit_window"] += not ("14:57:30" <= event.time().isoformat() < "15:00:00")
                    checks["status_not_18"] += number(r.get("market_status")) != 18
                    checks["invalid_price"] += (number(r.get("proxy_close_price")) or 0) <= 0
                summary["execution_capture_checks"] = dict(checks)
                summary["quote_age_seconds_min_max"] = [min(ages), max(ages)] if ages else None
                totals.update(checks)
            elif name == "etf_order.csv":
                summary["statuses"] = dict(Counter(r["status"] for r in rows))
                summary["environments"] = dict(Counter(r["env"] for r in rows))
                summary["filled_rows"] = sum((number(r["traded_volume"]) or 0) > 0 for r in rows)
                summary["broker_fill_rows"] = sum((number(r["traded_volume"]) or 0) > 0 and r["env"] == "live" and r["status"] != "SIMULATED_FILLED" for r in rows)
                totals["order_rows"] += len(rows)
                totals["broker_fill_rows"] += summary["broker_fill_rows"]
            elif name == "etf_context.csv":
                summary["position_maps_sizes"] = dict(Counter(position_map_size(r["positions"]) for r in rows))
                summary["has_frozen_cash_field"] = bool(rows and "frozen_cash" in rows[0])
                summary["has_full_account_market_value_field"] = bool(rows and "market_value" in rows[0])
            item["files"][name] = summary

        tick_dir = DATA / "data/market_tick/csv" / day.replace("-", "")
        item["tick_inventory_count"] = len(list(tick_dir.glob("*.csv")))
        for symbol in chosen:
            path = tick_dir / (symbol + ".csv")
            if not path.exists():
                cases.append({"date": day, "symbol": symbol, "exists": False})
                continue
            rows = read(path)
            counts = Counter()
            usable_times = []
            cutoff = datetime.fromisoformat(day + "T14:57:00").replace(tzinfo=TZ)
            seen = set()
            for r in rows:
                counts["rows"] += 1
                slot = r.get("slot_time")
                counts["duplicate_slot"] += slot in seen
                seen.add(slot)
                received = timestamp(r.get("captured_at"))
                quote = timestamp(r.get("quote_time"))
                if received is None or quote is None:
                    counts["invalid_timestamp"] += 1
                    continue
                age = (received - quote).total_seconds()
                counts["future_quote"] += age < 0
                counts["fetch_ok"] += r.get("fetch_status") == "ok"
                counts["flagged_stale"] += str(r.get("is_stale")).lower() == "true"
                counts["received_by_exact_145700"] += received <= cutoff
                if r.get("fetch_status") == "ok" and (number(r.get("last_price")) or 0) > 0 and number(r.get("stock_status")) == 18 and cutoff <= quote <= received and age <= 30:
                    usable_times.append(received.isoformat(timespec="milliseconds"))
            cases.append({"date": day, "symbol": symbol, "exists": True, "columns": list(rows[0]) if rows else [], "checks": dict(counts), "first_usable_capture_time": min(usable_times) if usable_times else None})
        logs.append(item)

    engine_paths = [
        "sartre_core/strategies/etf_rotation_core.py", "sartre_core/strategies/macd_core.py",
        "sartre_core/config/etf_rotation_config.json", "sartre_core/adapters/miniqmt_closing_auction_mixin.py",
        "sartre_core/adapters/miniqmt_market_account_mixin.py", "sartre_core/adapters/miniqmt_portfolio_mixin.py",
        "sartre_core/adapters/miniqmt_stock_execution_mixin.py", "sartre_core/adapters/miniqmt_order_policy_gateway.py",
        "sartre_core/engine/order_policies.py", "sartre_core/engine/execution_modules.py",
        "sartre_core/simulate/shadow_account.py", "sartre_risk/risk_manager.py",
    ]
    original_paths = [DATA / "data/market_kline/csv/1d/none", DATA / "data/market_kline/parquet/1d/none"]
    return {
        "identity": plan["identity"], "evidence_ceiling": "L0", "formal_backtests": 0,
        "plan_sha256": digest(PLAN), "script_sha256": digest(Path(__file__)),
        "engineering_root": ENGINE.as_posix(),
        "engineering_hashes": {p: digest(ENGINE / p) for p in engine_paths},
        "sdk_visibility": {"runtime": "bundled Python only; no claim about other installations", "xtquant_spec_found": importlib.util.find_spec("xtquant") is not None},
        "raw_dayline_inventory": {p.relative_to(ROOT).as_posix(): sorted(f.name for f in p.glob("*.csv" if "csv" in p.parts else "*.parquet")) for p in original_paths},
        "derived_event_or_factor_files": "Not located by targeted filename searches in QMTData/data; absence is not a global filesystem proof.",
        "selection": {"dates": plan["dates"], "tick_symbols": chosen, "tick_case_count": len(cases)},
        "totals": dict(totals), "log_diagnostics": logs, "tick_case_studies": cases,
        "limitations": ["capture rows are polling observations; not proof of the exact ranking input or last-trade timestamp", "execution audit event times have limited precision; subsecond age signs require care", "sim fills cannot replace broker lifecycle or distributions", "no historical raw ETF dayline or validated factor mapping", "current pool and archived logs do not provide point-in-time universe"],
        "inputs": inputs,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(TOPIC) or out.exists():
        raise SystemExit("Output must be a new versioned artifact inside the ETF topic")
    result = audit()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": out.as_posix(), "selected": result["selection"], "totals": result["totals"], "input_files": len(result["inputs"]), "tick_file_counts": [r["tick_inventory_count"] for r in result["log_diagnostics"]]}, ensure_ascii=False))
