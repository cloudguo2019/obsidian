"""Generate date-only diagnostics for the HD-ANCHOR-001 stage-6 split.

This script deliberately reads no OHLC, return, signal, order, position, NAV, or
benchmark-result field.  It only resolves chronological boundaries, counts
available sessions, and audits point-in-time dividend coverage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, time, timezone, timedelta
from pathlib import Path


CST = timezone(timedelta(hours=8))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_sessions(path: Path) -> tuple[list[date], list[date]]:
    all_rows: list[date] = []
    trading: list[date] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        allowed = {"session_date", "trade_status"}
        missing = allowed.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"cleaned price is missing fields: {sorted(missing)}")
        for row in reader:
            session = parse_date(row["session_date"])
            all_rows.append(session)
            if row["trade_status"] == "TRADING":
                trading.append(session)
    if len(trading) != len(set(trading)):
        raise ValueError("duplicate trading sessions")
    return sorted(all_rows), sorted(trading)


def read_pit(path: Path) -> list[dict[str, datetime | str | None]]:
    records: list[dict[str, datetime | str | None]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {
            "record_id",
            "available_time",
            "effective_time",
            "expiry_time",
            "superseded_time",
        }
        missing = fields.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"PIT source is missing fields: {sorted(missing)}")
        for row in reader:
            records.append(
                {
                    "record_id": row["record_id"],
                    "available_time": parse_datetime(row["available_time"]),
                    "effective_time": parse_datetime(row["effective_time"]),
                    "expiry_time": parse_datetime(row["expiry_time"]),
                    "superseded_time": parse_datetime(row["superseded_time"]),
                }
            )
    return records


def first_session_on_or_after(sessions: list[date], anchor: date) -> date:
    for session in sessions:
        if session >= anchor:
            return session
    raise ValueError(f"no trading session on or after {anchor.isoformat()}")


def valid_pit_record(
    decision_time: datetime, records: list[dict[str, datetime | str | None]]
) -> str | None:
    eligible: list[dict[str, datetime | str | None]] = []
    for record in records:
        available = record["available_time"]
        effective = record["effective_time"]
        expiry = record["expiry_time"]
        superseded = record["superseded_time"]
        if not isinstance(available, datetime) or not isinstance(effective, datetime):
            continue
        if available > decision_time or effective > decision_time:
            continue
        if isinstance(expiry, datetime) and decision_time >= expiry:
            continue
        if isinstance(superseded, datetime) and decision_time >= superseded:
            continue
        eligible.append(record)
    if not eligible:
        return None
    latest = max(eligible, key=lambda item: item["effective_time"])
    return str(latest["record_id"])


def summarize_window(
    name: str,
    role: str,
    start: date,
    end_exclusive: date,
    all_rows: list[date],
    trading: list[date],
    pit: list[dict[str, datetime | str | None]],
) -> dict[str, object]:
    rows = [d for d in all_rows if start <= d < end_exclusive]
    sessions = [d for d in trading if start <= d < end_exclusive]
    valid = 0
    invalid_dates: list[str] = []
    for session in sessions:
        decision = datetime.combine(session, time(15, 0), tzinfo=CST)
        if valid_pit_record(decision, pit) is None:
            invalid_dates.append(session.isoformat())
        else:
            valid += 1
    return {
        "name": name,
        "role": role,
        "start_inclusive": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "last_observed_session": sessions[-1].isoformat() if sessions else None,
        "cleaned_calendar_rows": len(rows),
        "trading_sessions": len(sessions),
        "suspended_or_missing_rows": len(rows) - len(sessions),
        "valid_pit_sessions": valid,
        "invalid_pit_sessions": len(invalid_dates),
        "pit_coverage_ratio": round(valid / len(sessions), 9) if sessions else None,
        "invalid_pit_dates": invalid_dates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.workspace.resolve()
    price_path = root / "research/topics/high_dividend_bond/datasets/cleaned/cleaned_price.csv"
    pit_path = root / "research/topics/high_dividend_bond/datasets/cleaned/point_in_time_dividend_estimates.csv"

    all_rows, trading = read_sessions(price_path)
    pit = read_pit(pit_path)

    anchor_dates = [
        date(2018, 9, 10),
        date(2021, 9, 10),
        date(2022, 3, 10),
        date(2022, 9, 10),
        date(2023, 3, 10),
        date(2023, 9, 10),
        date(2024, 3, 10),
        date(2024, 9, 10),
        date(2025, 3, 10),
        date(2025, 9, 10),
        date(2026, 3, 10),
    ]
    resolved = {anchor: first_session_on_or_after(trading, anchor) for anchor in anchor_dates}
    study_end_exclusive = date(2026, 9, 10)

    definitions: list[tuple[str, str, date, date]] = [
        ("DEV", "development", resolved[date(2018, 9, 10)], resolved[date(2021, 9, 10)]),
        ("VAL", "validation", resolved[date(2021, 9, 10)], resolved[date(2022, 3, 10)]),
    ]
    rolling_anchors = [
        date(2022, 3, 10),
        date(2022, 9, 10),
        date(2023, 3, 10),
        date(2023, 9, 10),
        date(2024, 3, 10),
        date(2024, 9, 10),
        date(2025, 3, 10),
        date(2025, 9, 10),
    ]
    for index, (left, right) in enumerate(zip(rolling_anchors, rolling_anchors[1:]), start=1):
        definitions.append(
            (f"ROOS-{index:02d}", "retrospective_rolling_oos", resolved[left], resolved[right])
        )
    definitions.extend(
        [
            (
                "PLOCK-01",
                "retrospective_pseudo_lock",
                resolved[date(2025, 9, 10)],
                resolved[date(2026, 3, 10)],
            ),
            (
                "PLOCK-02",
                "retrospective_pseudo_lock",
                resolved[date(2026, 3, 10)],
                study_end_exclusive,
            ),
        ]
    )

    windows = [
        summarize_window(name, role, start, end, all_rows, trading, pit)
        for name, role, start, end in definitions
    ]

    development_start = resolved[date(2018, 9, 10)]
    first_index = trading.index(development_start)
    if first_index < 300:
        raise ValueError("fewer than 300 trading sessions are available for warm-up")
    warmup_sessions = trading[first_index - 300 : first_index]

    payload = {
        "statement_type": "计算结果",
        "pipeline_version": "HD-STAGE6-SPLIT-1.0.0",
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "data_cutoff": trading[-1].isoformat(),
        "inputs": {
            str(price_path.relative_to(root)).replace("\\", "/"): {
                "sha256": sha256(price_path),
                "fields_read": ["session_date", "trade_status"],
            },
            str(pit_path.relative_to(root)).replace("\\", "/"): {
                "sha256": sha256(pit_path),
                "fields_read": [
                    "record_id",
                    "available_time",
                    "effective_time",
                    "expiry_time",
                    "superseded_time",
                ],
            },
        },
        "forbidden_fields_read": [],
        "performance_calculation_count": 0,
        "strategy_run_count": 0,
        "locked_result_open_count": 0,
        "boundary_rule": "calendar anchors resolved to the first observed TRADING session on or after each anchor; intervals are left-closed and right-open",
        "resolved_boundaries": {
            anchor.isoformat(): session.isoformat() for anchor, session in resolved.items()
        },
        "warmup": {
            "trading_sessions": len(warmup_sessions),
            "start_inclusive": warmup_sessions[0].isoformat(),
            "end_exclusive": development_start.isoformat(),
            "last_session": warmup_sessions[-1].isoformat(),
            "produces_signals_or_returns": False,
        },
        "windows": windows,
        "prospective_confirmation": {
            "collection_start": "first eligible SSE session strictly after the final stage-6 freeze timestamp",
            "prelock_months": 24,
            "locked_months": 12,
            "lock_start": "first eligible SSE session on or after collection_start + 24 calendar months",
            "lock_end_exclusive": "first eligible SSE session on or after collection_start + 36 calendar months",
            "status": "NOT_YET_COLLECTED",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
