from __future__ import annotations

import csv
import hashlib
import json
import platform
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd


SCRIPT_VERSION = "HD-STAGE4-PREP-1.0.0"
TIMEZONE = "Asia/Shanghai"
PRICE_LIMIT_RATE = Decimal("0.10")
PRICE_TICK = Decimal("0.01")

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[4]
TOPIC_ROOT = SCRIPT_PATH.parents[1]
DATASET_ROOT = TOPIC_ROOT / "datasets"
DERIVED_ROOT = DATASET_ROOT / "derived"
SCHEDULE_ROOT = DATASET_ROOT / "schedules"

PRICE_PATH = REPO_ROOT / "research/QMTData/data/market_kline/csv/1d/none/600900.SH.csv"
CALENDAR_PATH = REPO_ROOT / "research/topics/trade_calendar/sse_trade_calendar_19901219_20260909.csv"
ACTION_PATH = DATASET_ROOT / "600900_cash_dividend_actions_2004_2026.csv"
DIVIDEND_ESTIMATE_CANDIDATE_PATH = DATASET_ROOT / "600900_expected_annual_dividend_per_share_2021_2026.md"
FEE_SOURCE_PATH = REPO_ROOT / "research/topics/A股交易税费历史版本表_截至2026-09-09.md"

ENRICHED_CSV_PATH = DERIVED_ROOT / "600900_daily_enriched_v1.csv"
TRANSACTION_COST_PATH = SCHEDULE_ROOT / "a_share_transaction_cost_schedule_v1.csv"
DIVIDEND_TAX_PATH = SCHEDULE_ROOT / "prc_listed_dividend_tax_schedule_v1.csv"
MANIFEST_PATH = DATASET_ROOT / "stage4_input_manifest_v1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def q2(value: Decimal) -> Decimal:
    return value.quantize(PRICE_TICK, rounding=ROUND_HALF_UP)


def decimal_or_none(value: object) -> Decimal | None:
    text = str(value or "").strip()
    return Decimal(text) if text else None


def date_or_none(value: object) -> date | None:
    text = str(value or "").strip()
    return date.fromisoformat(text) if text else None


def load_reference_actions() -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    with ACTION_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            is_valid_cash = row["record_status"] == "VALID" and row["action_type"] == "CASH_DIVIDEND"
            is_price_reference_only = (
                row["record_status"] == "QUARANTINED"
                and row["action_type"] == "OTHER"
                and bool(str(row["share_transfer_per_share"] or "").strip())
            )
            if not (is_valid_cash or is_price_reference_only):
                continue
            groups[row["action_group_id"]].append(row)

    actions: list[dict[str, object]] = []
    for group_id, rows in groups.items():
        ex_dates = {date_or_none(row["ex_date"]) for row in rows}
        if None in ex_dates or len(ex_dates) != 1:
            raise ValueError(f"Invalid ex-date group: {group_id}")

        explicit_refs = {
            decimal_or_none(row["ex_reference_dividend_per_share"])
            for row in rows
            if decimal_or_none(row["ex_reference_dividend_per_share"]) is not None
        }
        if len(explicit_refs) > 1:
            raise ValueError(f"Conflicting ex-reference dividends: {group_id}")

        if explicit_refs:
            cash_reference = next(iter(explicit_refs))
            cash_method = "EXPLICIT_EX_REFERENCE_DIVIDEND"
        else:
            cash_values = [decimal_or_none(row["cash_dividend_per_share"]) for row in rows]
            cash_reference = max(value for value in cash_values if value is not None)
            cash_method = "PUBLIC_HOLDER_MAX_CASH_WITHIN_GROUP"

        transfer_values = [decimal_or_none(row["share_transfer_per_share"]) for row in rows]
        transfer_reference = max(
            (value for value in transfer_values if value is not None),
            default=Decimal("0"),
        )
        actions.append(
            {
                "group_id": group_id,
                "ex_date": next(iter(ex_dates)),
                "cash_reference": cash_reference,
                "transfer_reference": transfer_reference,
                "method": cash_method,
            }
        )
    return sorted(actions, key=lambda item: (item["ex_date"], item["group_id"]))


def apply_reference_actions(
    previous_close: Decimal,
    previous_date: date,
    current_date: date,
    actions: list[dict[str, object]],
) -> tuple[Decimal, list[str], list[str]]:
    reference = previous_close
    applied_ids: list[str] = []
    methods: list[str] = []
    for action in actions:
        ex_date = action["ex_date"]
        if not isinstance(ex_date, date) or not (previous_date < ex_date <= current_date):
            continue
        cash_reference = action["cash_reference"]
        transfer_reference = action["transfer_reference"]
        if not isinstance(cash_reference, Decimal) or not isinstance(transfer_reference, Decimal):
            raise TypeError(f"Invalid reference action: {action['group_id']}")
        reference = q2((reference - cash_reference) / (Decimal("1") + transfer_reference))
        applied_ids.append(str(action["group_id"]))
        methods.append(str(action["method"]))
    return reference, applied_ids, methods


def build_enriched_daily() -> tuple[pd.DataFrame, dict[str, object]]:
    raw = pd.read_csv(PRICE_PATH, dtype={"symbol": "string", "period": "string"})
    raw["session_date"] = pd.to_datetime(raw["datetime"], errors="raise").dt.date
    if raw.duplicated(["symbol", "period", "session_date", "adjust"]).any():
        raise ValueError("Duplicate source daily keys")
    if set(raw["symbol"].dropna().unique()) != {"600900.SH"}:
        raise ValueError("Unexpected symbol in price source")
    if set(raw["adjust"].dropna().unique()) != {"none"}:
        raise ValueError("Price source is not unadjusted")

    calendar = pd.read_csv(CALENDAR_PATH, dtype={"trade_date": "string"})
    calendar["session_date"] = pd.to_datetime(calendar["trade_date"], format="%Y%m%d").dt.date
    first_date = min(raw["session_date"])
    last_date = max(raw["session_date"])
    calendar = calendar[
        (calendar["exchange"] == "SSE")
        & (calendar["is_open"] == 1)
        & (calendar["session_date"] >= first_date)
        & (calendar["session_date"] <= last_date)
    ].copy()
    if calendar["session_date"].duplicated().any():
        raise ValueError("Duplicate calendar dates")

    raw_by_date = {row.session_date: row for row in raw.itertuples(index=True)}
    actions = load_reference_actions()
    source_hash = sha256(PRICE_PATH)
    calendar_hash = sha256(CALENDAR_PATH)
    action_hash = sha256(ACTION_PATH)
    source_version = f"xtquant-export-none-1d-cutoff-{last_date.isoformat()}-sha256-{source_hash[:12]}"
    calendar_version = f"sse-trade-calendar-cutoff-2026-09-09-sha256-{calendar_hash[:12]}"
    action_version = f"600900-actions-v1-sha256-{action_hash[:12]}"

    rows: list[dict[str, object]] = []
    previous_observed_close: Decimal | None = None
    previous_observed_date: date | None = None
    limit_violations = 0
    action_adjusted_rows = 0

    for session_date in calendar["session_date"].tolist():
        raw_row = raw_by_date.get(session_date)
        base = {
            "session_date": session_date.isoformat(),
            "datetime": f"{session_date.isoformat()}T15:00:00+08:00",
            "timezone": TIMEZONE,
            "symbol": "600900.SH",
            "period": "1d",
            "adjust": "none",
            "source": "xtquant",
            "source_version": source_version,
            "calendar_source": "sina_finance_cross_checked_with_sse_2026_holidays",
            "calendar_version": calendar_version,
            "corporate_action_version": action_version,
            "pipeline_version": SCRIPT_VERSION,
        }
        if raw_row is None:
            rows.append(
                {
                    **base,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                    "volume_raw_lots": None,
                    "amount_cny": None,
                    "pre_close": None,
                    "trade_status": "SUSPENDED_OR_MISSING",
                    "trade_status_method": "SSE_OPEN_SESSION_WITHOUT_XTQUANT_DAILY_BAR",
                    "limit_up": None,
                    "limit_down": None,
                    "price_limit_rate": None,
                    "price_limit_method": "NOT_APPLICABLE_NO_BAR",
                    "price_limit_evidence": "C",
                    "reference_action_ids": "",
                    "reference_action_methods": "",
                    "limit_validation": "NOT_TESTABLE",
                    "raw_record_id": "",
                }
            )
            continue

        source_line = int(raw_row.Index) + 2
        close = Decimal(str(raw_row.close))
        high = q2(Decimal(str(raw_row.high)))
        low = q2(Decimal(str(raw_row.low)))
        applied_ids: list[str] = []
        action_methods: list[str] = []
        if previous_observed_close is None or previous_observed_date is None:
            pre_close = None
            limit_up = None
            limit_down = None
            limit_rate = None
            limit_method = "NO_LIMIT_FIRST_LISTING_OBSERVATION"
            limit_evidence = "C"
            validation = "NOT_TESTABLE"
        else:
            pre_close, applied_ids, action_methods = apply_reference_actions(
                previous_observed_close,
                previous_observed_date,
                session_date,
                actions,
            )
            if applied_ids:
                action_adjusted_rows += 1
            limit_up = q2(pre_close * (Decimal("1") + PRICE_LIMIT_RATE))
            limit_down = q2(pre_close * (Decimal("1") - PRICE_LIMIT_RATE))
            limit_rate = PRICE_LIMIT_RATE
            limit_method = "DERIVED_SSE_MAIN_BOARD_10PCT_FROM_REFERENCE_V1"
            limit_evidence = "B"
            validation = "PASS" if high <= limit_up and low >= limit_down else "VIOLATION"
            if validation == "VIOLATION":
                limit_violations += 1

        rows.append(
            {
                **base,
                "open": raw_row.open,
                "high": raw_row.high,
                "low": raw_row.low,
                "close": raw_row.close,
                "volume_raw_lots": raw_row.volume,
                "amount_cny": raw_row.amount,
                "pre_close": float(pre_close) if pre_close is not None else None,
                "trade_status": "TRADING",
                "trade_status_method": "XTQUANT_POSITIVE_OHLC_AND_NONZERO_VOLUME_BAR",
                "limit_up": float(limit_up) if limit_up is not None else None,
                "limit_down": float(limit_down) if limit_down is not None else None,
                "price_limit_rate": float(limit_rate) if limit_rate is not None else None,
                "price_limit_method": limit_method,
                "price_limit_evidence": limit_evidence,
                "reference_action_ids": "|".join(applied_ids),
                "reference_action_methods": "|".join(action_methods),
                "limit_validation": validation,
                "raw_record_id": f"research/QMTData/data/market_kline/csv/1d/none/600900.SH.csv#L{source_line}",
            }
        )
        previous_observed_close = close
        previous_observed_date = session_date

    frame = pd.DataFrame(rows)
    summary = {
        "calendar_session_count": len(frame),
        "trading_bar_count": int((frame["trade_status"] == "TRADING").sum()),
        "suspended_or_missing_count": int((frame["trade_status"] == "SUSPENDED_OR_MISSING").sum()),
        "action_adjusted_reference_rows": action_adjusted_rows,
        "price_limit_validation_violations": limit_violations,
        "first_session": frame["session_date"].min(),
        "last_session": frame["session_date"].max(),
    }
    return frame, summary


def transaction_cost_rows() -> list[dict[str, object]]:
    source_url = "research/topics/A股交易税费历史版本表_截至2026-09-09.md"
    rows = [
        ("STAMP_TAX", "2001-11-16", "2005-01-23", "BOTH", "transaction_amount", "0.002", "official_history", "A", ""),
        ("STAMP_TAX", "2005-01-24", "2007-05-29", "BOTH", "transaction_amount", "0.001", "official", "A", ""),
        ("STAMP_TAX", "2007-05-30", "2008-04-23", "BOTH", "transaction_amount", "0.003", "official_history", "A", ""),
        ("STAMP_TAX", "2008-04-24", "2008-09-18", "BOTH", "transaction_amount", "0.001", "official", "A", ""),
        ("STAMP_TAX", "2008-09-19", "2023-08-27", "SELL", "transaction_amount", "0.001", "official", "A", ""),
        ("STAMP_TAX", "2023-08-28", "", "SELL", "transaction_amount", "0.0005", "official", "A", ""),
        ("TRANSFER_FEE", "", "2012-05-31", "BOTH", "nominal_value", "0.001", "historical_archive_start_unknown", "C", "Exact early effective start unresolved"),
        ("TRANSFER_FEE", "2012-06-01", "2012-08-31", "BOTH", "nominal_value", "0.00075", "official", "A", "Shanghai investor total"),
        ("TRANSFER_FEE", "2012-09-01", "2015-07-31", "BOTH", "nominal_value", "0.0006", "official", "A", "Shanghai investor total"),
        ("TRANSFER_FEE", "2015-08-01", "2022-04-28", "BOTH", "transaction_amount", "0.00002", "official", "A", ""),
        ("TRANSFER_FEE", "2022-04-29", "", "BOTH", "transaction_amount", "0.00001", "official", "A", ""),
        ("HANDLING_FEE", "", "2012-05-31", "BOTH", "transaction_amount", "", "incomplete_history", "C", "No continuous verified rate in source document"),
        ("HANDLING_FEE", "2012-06-01", "2012-08-31", "BOTH", "transaction_amount", "0.000087", "official", "A", ""),
        ("HANDLING_FEE", "2012-09-01", "2015-07-31", "BOTH", "transaction_amount", "0.0000696", "official", "A", ""),
        ("HANDLING_FEE", "2015-08-01", "2023-08-27", "BOTH", "transaction_amount", "0.0000487", "official", "A", "SSE 2023 adjustment notice explicitly identifies this prior standard"),
        ("HANDLING_FEE", "2023-08-28", "", "BOTH", "transaction_amount", "0.0000341", "official", "A", ""),
        ("REGULATORY_FEE", "2003-01-01", "2011-12-31", "BOTH", "transaction_amount", "0.00004", "official_history", "A", ""),
        ("REGULATORY_FEE", "2012-01-01", "", "BOTH", "transaction_amount", "0.00002", "official", "A", ""),
        ("BROKER_COMMISSION", "2003-11-18", "", "BOTH", "transaction_amount", "0.0001", "preregistered_assumption", "C", "Minimum CNY 5 per parent order; modeled separately from statutory fees"),
    ]
    return [
        {
            "fee_type": fee_type,
            "market": "SSE_A_SHARE",
            "effective_start": start,
            "effective_end": end,
            "charge_side": side,
            "rate_basis": basis,
            "rate_decimal": rate,
            "minimum_cny_per_parent_order": "5" if fee_type == "BROKER_COMMISSION" else "",
            "commission_interaction": "BROKER_BASE" if fee_type == "BROKER_COMMISSION" else "ADD_SEPARATELY",
            "source_kind": source_kind,
            "evidence_level": evidence,
            "source_document": source_url,
            "version": "A_SHARE_COST_SCHEDULE_V1_20260910",
            "note": note,
        }
        for fee_type, start, end, side, basis, rate, source_kind, evidence, note in rows
    ]


def dividend_tax_rows() -> list[dict[str, object]]:
    rows = [
        ("PRC_LISTED_DIVIDEND_PIT_PRE_2005_102", "", "2005-06-12", "UNRESOLVED", "", "UNRESOLVED", "C", "Pre-policy historical rate not yet frozen"),
        ("PRC_LISTED_DIVIDEND_PIT_2005_102", "2005-06-13", "2012-12-31", "ALL_HOLDING_PERIODS", "0.10", "AT_PAYMENT", "A", "Reduced taxable income produced effective 10%"),
        ("PRC_LISTED_DIVIDEND_PIT_2012_85", "2013-01-01", "2015-09-07", "LE_1_CALENDAR_MONTH", "0.20", "FINAL_BY_HOLDING_PERIOD", "A", "Initial withholding 5%; supplementary collection later"),
        ("PRC_LISTED_DIVIDEND_PIT_2012_85", "2013-01-01", "2015-09-07", "GT_1_CALENDAR_MONTH_LE_1_YEAR", "0.10", "FINAL_BY_HOLDING_PERIOD", "A", "Initial withholding 5%; supplementary collection later"),
        ("PRC_LISTED_DIVIDEND_PIT_2012_85", "2013-01-01", "2015-09-07", "GT_1_YEAR", "0.05", "FINAL_BY_HOLDING_PERIOD", "A", "Initial withholding 5%"),
        ("PRC_LISTED_DIVIDEND_PIT_2015_101_PLUS_2012_85", "2015-09-08", "", "LE_1_CALENDAR_MONTH", "0.20", "SUPPLEMENT_AT_SALE", "A", "Gross dividend paid first"),
        ("PRC_LISTED_DIVIDEND_PIT_2015_101_PLUS_2012_85", "2015-09-08", "", "GT_1_CALENDAR_MONTH_LE_1_YEAR", "0.10", "SUPPLEMENT_AT_SALE", "A", "Gross dividend paid first"),
        ("PRC_LISTED_DIVIDEND_PIT_2015_101_PLUS_2012_85", "2015-09-08", "", "GT_1_YEAR", "0.00", "NO_TAX_OVER_ONE_YEAR", "A", "Gross dividend paid first"),
    ]
    sources = {
        "PRC_LISTED_DIVIDEND_PIT_2005_102": "https://shanghai.chinatax.gov.cn/zcfw/zcfgk/grsds/200507/t288852.html",
        "PRC_LISTED_DIVIDEND_PIT_2012_85": "https://fgk.chinatax.gov.cn/zcfgk/c102416/c5204415/content.html",
        "PRC_LISTED_DIVIDEND_PIT_2015_101_PLUS_2012_85": "https://www.chinatax.gov.cn/chinatax/n810341/n810765/n1465977/n1466017/c1967339/content.html",
    }
    return [
        {
            "tax_rule_version": version,
            "effective_start": start,
            "effective_end": end,
            "holding_period_condition": holding_condition,
            "tax_rate_decimal": rate,
            "collection_timing": timing,
            "initial_withholding_rate_decimal": "0.05" if version == "PRC_LISTED_DIVIDEND_PIT_2012_85" else "",
            "account_scope": "PRC_RESIDENT_INDIVIDUAL_A_SHARE",
            "source_url": sources.get(version, ""),
            "source_document": "research/topics/high_dividend_bond/datasets/600900_cash_dividend_actions_2004_2026.md",
            "evidence_level": evidence,
            "version": "PRC_LISTED_DIVIDEND_TAX_SCHEDULE_V1_20260910",
            "note": note,
        }
        for version, start, end, holding_condition, rate, timing, evidence, note in rows
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    for required in (PRICE_PATH, CALENDAR_PATH, ACTION_PATH, DIVIDEND_ESTIMATE_CANDIDATE_PATH, FEE_SOURCE_PATH):
        if not required.exists():
            raise FileNotFoundError(required)

    DERIVED_ROOT.mkdir(parents=True, exist_ok=True)
    SCHEDULE_ROOT.mkdir(parents=True, exist_ok=True)
    enriched, audit = build_enriched_daily()
    enriched.to_csv(ENRICHED_CSV_PATH, index=False, encoding="utf-8", float_format="%.6f")
    write_csv(TRANSACTION_COST_PATH, transaction_cost_rows())
    write_csv(DIVIDEND_TAX_PATH, dividend_tax_rows())

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest = {
        "manifest_version": "HD-STAGE4-INPUT-MANIFEST-1.0",
        "generated_at": generated_at,
        "timezone": TIMEZONE,
        "pipeline_version": SCRIPT_VERSION,
        "pipeline": {
            "path": str(SCRIPT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": sha256(SCRIPT_PATH),
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
        },
        "formal_backtest_run_count": 0,
        "inputs": [
            {"path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"), "sha256": sha256(path), "size_bytes": path.stat().st_size}
            for path in (PRICE_PATH, CALENDAR_PATH, ACTION_PATH, DIVIDEND_ESTIMATE_CANDIDATE_PATH, FEE_SOURCE_PATH)
        ],
        "outputs": [
            {"path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"), "sha256": sha256(path), "size_bytes": path.stat().st_size}
            for path in (ENRICHED_CSV_PATH, TRANSACTION_COST_PATH, DIVIDEND_TAX_PATH)
        ],
        "daily_audit": audit,
        "limitations": [
            "trade_status=TRADING is inferred from a valid nonzero Xtquant daily bar, not a historical exchange status file.",
            "SUSPENDED_OR_MISSING intentionally combines suspension and absent vendor data and fails closed for trading.",
            "limit_up/limit_down are rule-derived evidence level B, not direct historical Xtquant fields.",
            "Handling-fee history before 2012 remains incomplete; this does not affect the preregistered primary period beginning in 2018.",
            "The research cost model treats the 0.01% broker commission as separate from statutory fees; broker-statement all-in semantics remain a later external-validity check.",
            "The stage-4 enriched table is CSV; cleaned_price.parquet remains a stage-5 output because no parquet engine is bundled in the current runtime.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outputs": manifest["outputs"], "daily_audit": audit}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
