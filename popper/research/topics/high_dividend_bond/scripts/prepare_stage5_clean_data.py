#!/usr/bin/env python3
"""Prepare and audit Stage-5 datasets for HD-ANCHOR-001.

This program performs no strategy simulation. It reads immutable/source-like inputs,
normalizes types into new files, records every transformation class, validates the
PIT rules, and writes reproducibility hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


PIPELINE_VERSION = "HD-STAGE5-CLEAN-1.0.0"
TZ = "Asia/Shanghai"
PIT_METHOD = "SHAREHOLDER_MEETING_CONFIRMED_ANNUAL_DPS_V1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def first_open_after(announcement_date: pd.Timestamp, open_dates: pd.DatetimeIndex) -> pd.Timestamp:
    candidates = open_dates[open_dates > announcement_date.normalize()]
    if len(candidates) == 0:
        return pd.NaT
    return candidates.min()


def check(name: str, observed: object, expected: object, passed: bool, severity: str = "ERROR") -> dict[str, object]:
    return {
        "check_id": name,
        "observed": observed,
        "expected": expected,
        "passed": bool(passed),
        "severity": severity,
    }


def log_row(
    log_id: str,
    dataset: str,
    action: str,
    reason: str,
    before_rows: int,
    after_rows: int,
    status: str = "APPLIED",
) -> dict[str, object]:
    return {
        "log_id": log_id,
        "dataset": dataset,
        "record_id": "ALL",
        "field": "MULTIPLE",
        "action": action,
        "old_value": "",
        "new_value": "",
        "reason": reason,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "evidence_level": "A",
        "status": status,
    }


def load_and_clean_price(path: Path) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    source = pd.read_csv(path, low_memory=False)
    cleaned = source.copy()
    before = len(cleaned)
    cleaned["session_date"] = pd.to_datetime(cleaned["session_date"], errors="coerce").dt.normalize()
    cleaned["datetime"] = pd.to_datetime(cleaned["datetime"], errors="coerce", utc=True).dt.tz_convert(TZ)
    numeric = [
        "open", "high", "low", "close", "volume_raw_lots", "amount_cny", "pre_close",
        "limit_up", "limit_down", "price_limit_rate",
    ]
    for column in numeric:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    cleaned = cleaned.sort_values(["symbol", "session_date"], kind="stable").reset_index(drop=True)

    missing_provenance = cleaned["raw_record_id"].isna()
    missing_provenance_count = int(missing_provenance.sum())
    cleaned.loc[missing_provenance, "raw_record_id"] = cleaned.loc[missing_provenance].apply(
        lambda row: (
            "research/topics/trade_calendar/sse_trade_calendar_19901219_20260909.csv"
            f"#trade_date={row['session_date']:%Y%m%d}|symbol={row['symbol']}|no_xtquant_bar"
        ),
        axis=1,
    )

    trading = cleaned["trade_status"].eq("TRADING")
    suspended = cleaned["trade_status"].eq("SUSPENDED_OR_MISSING")
    ohlc_valid = (
        (cleaned.loc[trading, "low"] <= cleaned.loc[trading, "open"])
        & (cleaned.loc[trading, "open"] <= cleaned.loc[trading, "high"])
        & (cleaned.loc[trading, "low"] <= cleaned.loc[trading, "close"])
        & (cleaned.loc[trading, "close"] <= cleaned.loc[trading, "high"])
    )
    price_positive = cleaned.loc[trading, ["open", "high", "low", "close"]].gt(0).all(axis=1)
    nonnegative_activity = cleaned.loc[trading, ["volume_raw_lots", "amount_cny"]].ge(0).all(axis=1)
    suspended_has_prices = cleaned.loc[suspended, ["open", "high", "low", "close"]].notna().any(axis=1)

    checks = [
        check("PRICE_REQUIRED_COLUMNS", int(len(source.columns)), ">=30", len(source.columns) >= 30),
        check("PRICE_NO_KEY_DUPLICATES", int(cleaned.duplicated(["symbol", "session_date"]).sum()), 0, not cleaned.duplicated(["symbol", "session_date"]).any()),
        check("PRICE_DATE_PARSE", int(cleaned["session_date"].isna().sum()), 0, cleaned["session_date"].notna().all()),
        check("PRICE_DATETIME_PARSE", int(cleaned["datetime"].isna().sum()), 0, cleaned["datetime"].notna().all()),
        check("PRICE_TIMEZONE", sorted(cleaned["timezone"].dropna().unique().tolist()), [TZ], cleaned["timezone"].eq(TZ).all()),
        check("PRICE_SOURCE", sorted(cleaned["source"].dropna().unique().tolist()), ["xtquant"], cleaned["source"].eq("xtquant").all()),
        check("PRICE_ADJUST_NONE", sorted(cleaned["adjust"].dropna().unique().tolist()), ["none"], cleaned["adjust"].eq("none").all()),
        check("PRICE_RAW_ID_COMPLETE", int(cleaned["raw_record_id"].isna().sum()), 0, cleaned["raw_record_id"].notna().all()),
        check("PRICE_RAW_ID_UNIQUE", int(cleaned["raw_record_id"].duplicated().sum()), 0, not cleaned["raw_record_id"].duplicated().any()),
        check("PRICE_TRADE_STATUS_DOMAIN", sorted(cleaned["trade_status"].dropna().unique().tolist()), ["SUSPENDED_OR_MISSING", "TRADING"], set(cleaned["trade_status"].dropna()) <= {"TRADING", "SUSPENDED_OR_MISSING"}),
        check("PRICE_OHLC_CONSTRAINT", int((~ohlc_valid).sum()), 0, ohlc_valid.all()),
        check("PRICE_POSITIVE", int((~price_positive).sum()), 0, price_positive.all()),
        check("PRICE_VOLUME_AMOUNT_NONNEGATIVE", int((~nonnegative_activity).sum()), 0, nonnegative_activity.all()),
        check("PRICE_SUSPENDED_NO_FAKE_OHLC", int(suspended_has_prices.sum()), 0, not suspended_has_prices.any()),
        check("PRICE_LIMIT_VALIDATION", int(cleaned["limit_validation"].eq("FAIL").sum()), 0, not cleaned["limit_validation"].eq("FAIL").any()),
        check("PRICE_NO_ROW_DROP", len(cleaned), before, len(cleaned) == before),
    ]
    logs = [
        log_row("S5-PRICE-001", "cleaned_price", "COPY_TO_NEW_DATASET", "保留阶段4增强表为只读输入；不在原文件上修改", before, len(cleaned)),
        log_row("S5-PRICE-002", "cleaned_price", "TYPE_NORMALIZE", "日期、时区时间戳和数值字段转换为显式类型", before, len(cleaned)),
        log_row("S5-PRICE-003", "cleaned_price", "FILL_PROVENANCE_ID", f"为{missing_provenance_count}条无Xtquant日K的市场开市日填入交易日历稳定行标识；不伪造行情", before, len(cleaned)),
        log_row("S5-PRICE-004", "cleaned_price", "STABLE_SORT", "按symbol与session_date稳定排序；不删除、不填补行情", before, len(cleaned)),
    ]
    return cleaned, checks, logs


def load_and_clean_pit(
    path: Path, calendar_path: Path
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    source = pd.read_csv(path, low_memory=False)
    cleaned = source.copy()
    before = len(cleaned)
    date_columns = ["event_date", "announcement_date"]
    timestamp_columns = ["available_time", "effective_time", "expiry_time", "superseded_time"]
    for column in date_columns:
        cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce").dt.normalize()
    for column in timestamp_columns:
        cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce", utc=True).dt.tz_convert(TZ)
    cleaned["fiscal_year"] = pd.to_numeric(cleaned["fiscal_year"], errors="coerce").astype("Int64")
    cleaned["expected_annual_dividend_per_share"] = pd.to_numeric(
        cleaned["expected_annual_dividend_per_share"], errors="coerce"
    )
    cleaned = cleaned.sort_values(["symbol", "available_time"], kind="stable").reset_index(drop=True)

    calendar = pd.read_csv(calendar_path)
    open_dates = pd.DatetimeIndex(pd.to_datetime(calendar.loc[calendar["is_open"].eq(1), "trade_date"].astype(str), format="%Y%m%d"))
    expected_available_dates = cleaned["announcement_date"].map(lambda value: first_open_after(value, open_dates))
    actual_available_dates = cleaned["available_time"].dt.tz_localize(None).dt.normalize()
    expected_expiry = cleaned["available_time"] + pd.Timedelta(days=365)
    next_available = cleaned["available_time"].shift(-1)
    superseded_match = cleaned["superseded_time"].iloc[:-1].reset_index(drop=True).equals(
        next_available.iloc[:-1].reset_index(drop=True)
    ) and pd.isna(cleaned["superseded_time"].iloc[-1])
    fiscal_year_end = pd.to_datetime(cleaned["fiscal_year"].astype(str) + "-12-31", errors="coerce")

    checks = [
        check("PIT_ROW_COUNT", len(cleaned), 23, len(cleaned) == 23),
        check("PIT_FISCAL_YEAR_RANGE", [int(cleaned["fiscal_year"].min()), int(cleaned["fiscal_year"].max())], [2003, 2025], cleaned["fiscal_year"].tolist() == list(range(2003, 2026))),
        check("PIT_NO_RECORD_ID_DUPLICATES", int(cleaned["record_id"].duplicated().sum()), 0, not cleaned["record_id"].duplicated().any()),
        check("PIT_NO_FISCAL_YEAR_DUPLICATES", int(cleaned["fiscal_year"].duplicated().sum()), 0, not cleaned["fiscal_year"].duplicated().any()),
        check("PIT_METHOD_FIXED", sorted(cleaned["estimate_method"].dropna().unique().tolist()), [PIT_METHOD], cleaned["estimate_method"].eq(PIT_METHOD).all()),
        check("PIT_EVENT_AFTER_FISCAL_YEAR_END", int((cleaned["event_date"] <= fiscal_year_end).sum()), 0, (cleaned["event_date"] > fiscal_year_end).all()),
        check("PIT_EVENT_NOT_AFTER_ANNOUNCEMENT", int((cleaned["event_date"] > cleaned["announcement_date"]).sum()), 0, (cleaned["event_date"] <= cleaned["announcement_date"]).all()),
        check("PIT_AVAILABLE_FIRST_OPEN_AFTER_ANNOUNCEMENT", int((actual_available_dates != expected_available_dates).sum()), 0, (actual_available_dates == expected_available_dates).all()),
        check("PIT_EFFECTIVE_EQUALS_AVAILABLE", int((cleaned["effective_time"] != cleaned["available_time"]).sum()), 0, cleaned["effective_time"].equals(cleaned["available_time"])),
        check("PIT_EXPIRY_PLUS_365_DAYS", int((cleaned["expiry_time"] != expected_expiry).sum()), 0, cleaned["expiry_time"].equals(expected_expiry)),
        check("PIT_SUPERSEDED_EQUALS_NEXT_AVAILABLE", bool(superseded_match), True, superseded_match),
        check("PIT_POSITIVE_DPS", int(cleaned["expected_annual_dividend_per_share"].le(0).sum()), 0, cleaned["expected_annual_dividend_per_share"].gt(0).all()),
        check("PIT_SOURCE_DOCUMENT_COMPLETE", int(cleaned["source_document"].isna().sum()), 0, cleaned["source_document"].notna().all()),
        check("PIT_SECONDARY_SOURCE_COMPLETE", int(cleaned["secondary_source_document"].isna().sum()), 0, cleaned["secondary_source_document"].notna().all()),
        check("PIT_EVIDENCE_LEVEL_DOMAIN", sorted(cleaned["evidence_level"].dropna().unique().tolist()), ["A", "B"], set(cleaned["evidence_level"].dropna()) <= {"A", "B"}),
        check("PIT_NO_ROW_DROP", len(cleaned), before, len(cleaned) == before),
    ]
    logs = [
        log_row("S5-PIT-001", "point_in_time_dividend_estimates", "COPY_TO_NEW_DATASET", "保留正式PIT源表为只读输入；不在原文件上修改", before, len(cleaned)),
        log_row("S5-PIT-002", "point_in_time_dividend_estimates", "TYPE_NORMALIZE", "日期、带时区时间戳、财年和DPS转换为显式类型", before, len(cleaned)),
        log_row("S5-PIT-003", "point_in_time_dividend_estimates", "STABLE_SORT", "按symbol与available_time稳定排序；不填补未知公告时分秒", before, len(cleaned)),
    ]
    return cleaned, checks, logs


def load_and_clean_actions(path: Path) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    source = pd.read_csv(path, low_memory=False)
    cleaned = source.copy()
    before = len(cleaned)
    dates = ["announcement_date", "record_date", "ex_date", "pay_date"]
    for column in dates:
        cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce").dt.normalize()
    numeric = ["cash_dividend_per_share", "ex_reference_dividend_per_share", "share_transfer_per_share"]
    for column in numeric:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    cleaned = cleaned.sort_values(["symbol", "ex_date", "action_id"], kind="stable").reset_index(drop=True)
    chronology = (
        (cleaned["announcement_date"] <= cleaned["record_date"])
        & (cleaned["record_date"] <= cleaned["ex_date"])
        & (cleaned["ex_date"] <= cleaned["pay_date"])
    )
    valid_cash = cleaned["record_status"].eq("VALID") & cleaned["action_type"].eq("CASH_DIVIDEND")
    checks = [
        check("ACTION_NO_ID_DUPLICATES", int(cleaned["action_id"].duplicated().sum()), 0, not cleaned["action_id"].duplicated().any()),
        check("ACTION_REQUIRED_DATES", int(cleaned[dates].isna().any(axis=1).sum()), 0, not cleaned[dates].isna().any(axis=1).any()),
        check("ACTION_DATE_CHRONOLOGY", int((~chronology).sum()), 0, chronology.all()),
        check("ACTION_STATUS_DOMAIN", sorted(cleaned["record_status"].dropna().unique().tolist()), ["QUARANTINED", "VALID"], set(cleaned["record_status"].dropna()) <= {"VALID", "QUARANTINED"}),
        check("ACTION_VALID_CASH_NONNEGATIVE", int(cleaned.loc[valid_cash, "cash_dividend_per_share"].lt(0).sum()), 0, cleaned.loc[valid_cash, "cash_dividend_per_share"].ge(0).all()),
        check("ACTION_SOURCE_DOCUMENT_COMPLETE", int(cleaned["source_document"].isna().sum()), 0, cleaned["source_document"].notna().all()),
        check("ACTION_RAW_ID_COMPLETE", int(cleaned["raw_record_id"].isna().sum()), 0, cleaned["raw_record_id"].notna().all()),
        check("ACTION_NO_ROW_DROP", len(cleaned), before, len(cleaned) == before),
    ]
    quarantined = int(cleaned["record_status"].eq("QUARANTINED").sum())
    logs = [
        log_row("S5-ACTION-001", "corporate_actions", "COPY_TO_NEW_DATASET", "保留公司行动源表为只读输入；不在原文件上修改", before, len(cleaned)),
        log_row("S5-ACTION-002", "corporate_actions", "TYPE_NORMALIZE", "日期与数值字段转换为显式类型", before, len(cleaned)),
        log_row("S5-ACTION-003", "corporate_actions", "RETAIN_QUARANTINED", f"保留{quarantined}条隔离记录并依赖record_status禁止进入年度现金分红逻辑", before, len(cleaned)),
    ]
    return cleaned, checks, logs


def coverage_stats(price: pd.DataFrame, pit: pd.DataFrame, start: str, end: str) -> dict[str, object]:
    sessions = price[
        price["trade_status"].eq("TRADING")
        & price["session_date"].between(pd.Timestamp(start), pd.Timestamp(end))
    ][["session_date"]].copy()
    sessions["decision_time"] = pd.to_datetime(sessions["session_date"].dt.strftime("%Y-%m-%d") + " 15:00:00").dt.tz_localize(TZ)
    intervals = []
    for row in pit.itertuples(index=False):
        interval_end = row.expiry_time
        if pd.notna(row.superseded_time):
            interval_end = min(interval_end, row.superseded_time - pd.Timedelta(microseconds=1))
        intervals.append((row.available_time, interval_end, row.record_id))
    def matching_record(moment: pd.Timestamp) -> str | None:
        eligible = [record_id for begin, finish, record_id in intervals if begin <= moment <= finish]
        return eligible[-1] if eligible else None
    sessions["pit_record_id"] = sessions["decision_time"].map(matching_record)
    covered = int(sessions["pit_record_id"].notna().sum())
    total = len(sessions)
    gaps = sessions.loc[sessions["pit_record_id"].isna(), "session_date"]
    return {
        "window_start": start,
        "window_end": end,
        "trading_sessions": total,
        "covered_sessions": covered,
        "uncovered_sessions": total - covered,
        "coverage_ratio": round(covered / total, 8) if total else None,
        "first_uncovered_session": gaps.min().date().isoformat() if len(gaps) else None,
        "last_uncovered_session": gaps.max().date().isoformat() if len(gaps) else None,
        "uncovered_session_list": gaps.dt.strftime("%Y-%m-%d").tolist(),
    }


def csv_ready(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if isinstance(result[column].dtype, pd.DatetimeTZDtype):
            result[column] = result[column].astype("string")
        elif pd.api.types.is_datetime64_any_dtype(result[column]):
            result[column] = result[column].dt.strftime("%Y-%m-%d")
    return result


def markdown_report(
    audit_time: str,
    price: pd.DataFrame,
    pit: pd.DataFrame,
    actions: pd.DataFrame,
    checks: list[dict[str, object]],
    coverage: dict[str, object],
    errors: list[dict[str, object]],
    warnings: list[dict[str, object]],
) -> str:
    trading = int(price["trade_status"].eq("TRADING").sum())
    suspended = int(price["trade_status"].eq("SUSPENDED_OR_MISSING").sum())
    evidence_counts = pit["evidence_level"].value_counts().sort_index().to_dict()
    meeting_counts = pit["approval_meeting_type"].value_counts().sort_index().to_dict()
    valid_actions = int(actions["record_status"].eq("VALID").sum())
    quarantined_actions = int(actions["record_status"].eq("QUARANTINED").sum())
    check_lines = "\n".join(
        f"| [计算结果｜A] `{item['check_id']}` | {item['observed']} | {item['expected']} | {'PASS' if item['passed'] else 'FAIL'} | {item['severity']} |"
        for item in checks
    )
    return f"""# HD-ANCHOR-001 阶段5数据清理和质量审计报告

> [已观察事实｜A] 审计时间：{audit_time}；流水线：`{PIPELINE_VERSION}`。本程序未运行策略、未读取锁定集结果、未修改原始文件。

## 1. 本阶段要回答的研究问题

[方法选择｜C] 判断日线、PIT分红和公司行动能否在不回填未来信息、不伪造停牌成交、不重复计算现金分红的前提下形成可复现的清洁输入。

## 2. 需要理解的理论和公式

[方法选择｜C] PIT有效条件为`available_time <= decision_time <= expiry_time`，且存在后继记录时必须满足`decision_time < superseded_time`。只有公告日期时，`available_time`等于公告日之后首个上交所交易日09:30（Asia/Shanghai）。

[方法选择｜C] OHLC约束为`low <= open/close <= high`；交易日价格必须为正、成交量和成交额非负。市场开市但无个股有效日K的日期保持`SUSPENDED_OR_MISSING`并禁止成交。

## 3. 本阶段实际操作

[已观察事实｜A] 三个源表均复制到新目录后进行显式类型转换和稳定排序；删除0行、行情插值0处、未知分红填0共0处。无Xtquant日K的市场开市日仅补充交易日历稳定来源标识，不补价格。所有操作类别记录在`cleaning_log.csv`。

## 4. 已直接执行的操作

[计算结果｜A] 价格表清理前后均为{len(price):,}行，其中`TRADING` {trading:,}行、`SUSPENDED_OR_MISSING` {suspended:,}行；日期范围{price['session_date'].min().date()}至{price['session_date'].max().date()}。

[计算结果｜A] 正式PIT表清理前后均为{len(pit)}行，财年范围{int(pit['fiscal_year'].min())}—{int(pit['fiscal_year'].max())}；会议类型计数为{meeting_counts}，证据等级计数为{evidence_counts}。

[计算结果｜A] 公司行动表清理前后均为{len(actions)}行，其中`VALID` {valid_actions}行、`QUARANTINED` {quarantined_actions}行；隔离行被保留但不能进入年度现金分红入账逻辑。

## 5. 仍需要研究者提供的数据或选择

[待办事项｜B] 为满足独立价格交叉核验，应归档一个不依赖Xtquant的600900未复权日线副源；这不阻止阶段5内部一致性审计，但在现行合同下继续阻止正式L2运行。

[待办事项｜C] 2012年前交易经手费连续历史仍不完整；预注册主研究期从2018年开始，故不影响主期，但影响更早期间的成本精确复算。

## 6. 本阶段产物及保存路径

[已观察事实｜A] 清洁Parquet与CSV镜像、清理日志、机器可读清单和本报告均保存在`research/topics/high_dividend_bond/datasets/cleaned/`。

## 7. 验收标准与结果

| 类型与检查 | 观察值 | 期望值 | 结果 | 严重度 |
|---|---:|---:|---|---|
{check_lines}

[计算结果｜A] 结构性错误数为{len(errors)}，警告数为{len(warnings)}。阶段5内部结构与时序审计结果为`{'PASS' if not errors else 'FAIL'}`。

[计算结果｜A] 2018-01-01至2026-09-09的有效交易日PIT覆盖率为{coverage['coverage_ratio']:.4%}（{coverage['covered_sessions']}/{coverage['trading_sessions']}），预注册门槛为至少80%；未覆盖交易日{coverage['uncovered_sessions']}个。

[计算结果｜A] 未覆盖交易日为：{', '.join(coverage['uncovered_session_list']) if coverage['uncovered_session_list'] else '无'}。这些日期来自相邻年度确认间隔超过365自然日形成的真实失效窗口，未进行无限期前向填充。

## 8. 已发现的问题和证据等级

[已观察事实｜A] FY2012与FY2013的年度DPS分别由临时股东大会确认，故方法名已在v1.3更正为“股东大会确认”，经济口径和365日有效期未改变。

[已观察事实｜B] FY2003的网上披露日和报纸刊登日存在日期差异；两种记录均不早于2004-05-17进入策略，源表保留差异说明。

[已知限制｜B] `trade_status`和涨跌停价是基于Xtquant日K、交易日历和交易所规则的派生字段，不是交易所逐日状态原始档案；`SUSPENDED_OR_MISSING`故意不把供应商缺失强行解释为停牌。

[已知限制｜B] PIT表有{int((pit['evidence_level'] == 'B').sum())}条B级历史记录；正式结论必须保留这一证据不确定性，不能把B级镜像当作交易所原始档案。

## 9. 是否允许进入下一阶段

[方法选择｜C] `{'允许在研究者确认后进入阶段6样本划分；正式L2/L3仍关闭' if not errors and coverage['coverage_ratio'] >= 0.8 else '不允许进入阶段6，先修复结构错误或PIT覆盖率'}`。阶段4数据合同与正式PIT输入已闭环；阶段6不得查看最终锁定集结果，正式回测授权仍为`false`。
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--price", type=Path, default=Path("research/topics/high_dividend_bond/datasets/derived/600900_daily_enriched_v1.csv"))
    parser.add_argument("--pit", type=Path, default=Path("research/topics/high_dividend_bond/datasets/600900_point_in_time_dividend_estimates_v1.csv"))
    parser.add_argument("--actions", type=Path, default=Path("research/topics/high_dividend_bond/datasets/600900_cash_dividend_actions_2004_2026.csv"))
    parser.add_argument("--calendar", type=Path, default=Path("research/topics/trade_calendar/sse_trade_calendar_19901219_20260909.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("research/topics/high_dividend_bond/datasets/cleaned"))
    args = parser.parse_args()
    root = args.root.resolve()
    resolve = lambda value: value if value.is_absolute() else root / value
    price_path, pit_path, action_path, calendar_path = map(resolve, [args.price, args.pit, args.actions, args.calendar])
    output_dir = resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    price, price_checks, price_logs = load_and_clean_price(price_path)
    pit, pit_checks, pit_logs = load_and_clean_pit(pit_path, calendar_path)
    actions, action_checks, action_logs = load_and_clean_actions(action_path)
    checks = price_checks + pit_checks + action_checks
    errors = [item for item in checks if not item["passed"] and item["severity"] == "ERROR"]
    warnings = [item for item in checks if not item["passed"] and item["severity"] == "WARNING"]
    coverage = coverage_stats(price, pit, "2018-01-01", "2026-09-09")
    checks.append(check("PIT_COVERAGE_2018_TO_CUTOFF", coverage["coverage_ratio"], ">=0.80", bool(coverage["coverage_ratio"] is not None and coverage["coverage_ratio"] >= 0.80)))
    errors = [item for item in checks if not item["passed"] and item["severity"] == "ERROR"]

    output_paths = {
        "price_csv": output_dir / "cleaned_price.csv",
        "price_parquet": output_dir / "cleaned_price.parquet",
        "pit_csv": output_dir / "point_in_time_dividend_estimates.csv",
        "pit_parquet": output_dir / "point_in_time_dividend_estimates.parquet",
        "actions_csv": output_dir / "corporate_actions.csv",
        "actions_parquet": output_dir / "corporate_actions.parquet",
        "log": output_dir / "cleaning_log.csv",
        "manifest": output_dir / "data_manifest.json",
        "report": output_dir / "data_audit_report.md",
    }
    csv_ready(price).to_csv(output_paths["price_csv"], index=False, encoding="utf-8-sig")
    csv_ready(pit).to_csv(output_paths["pit_csv"], index=False, encoding="utf-8-sig")
    csv_ready(actions).to_csv(output_paths["actions_csv"], index=False, encoding="utf-8-sig")
    price.to_parquet(output_paths["price_parquet"], index=False, engine="pyarrow")
    pit.to_parquet(output_paths["pit_parquet"], index=False, engine="pyarrow")
    actions.to_parquet(output_paths["actions_parquet"], index=False, engine="pyarrow")
    cleaning_log = pd.DataFrame(price_logs + pit_logs + action_logs)
    cleaning_log.to_csv(output_paths["log"], index=False, encoding="utf-8-sig")

    audit_time = datetime.now(ZoneInfo(TZ)).isoformat(timespec="seconds")
    report = markdown_report(audit_time, price, pit, actions, checks, coverage, errors, warnings)
    output_paths["report"].write_text(report, encoding="utf-8")

    input_files = [price_path, pit_path, action_path, calendar_path]
    optional_inputs = [
        root / "research/QMTData/data/market_kline/csv/1d/none/600900.SH.csv",
        root / "research/topics/high_dividend_bond/datasets/schedules/a_share_transaction_cost_schedule_v1.csv",
        root / "research/topics/high_dividend_bond/datasets/schedules/prc_listed_dividend_tax_schedule_v1.csv",
        root / "research/topics/high_dividend_bond/experiments/HD-ANCHOR-001/preregistration_v1.3_shareholder_meeting_confirmed.yaml",
        root / "research/topics/high_dividend_bond/datasets/data_contract_v1_3_shareholder_meeting_confirmed.md",
    ]
    input_files.extend(path for path in optional_inputs if path.exists())
    manifest_outputs = [path for key, path in output_paths.items() if key != "manifest"]
    manifest = {
        "statement_type": "计算结果",
        "manifest_version": "HD-STAGE5-DATA-MANIFEST-1.0",
        "generated_at": audit_time,
        "timezone": TZ,
        "pipeline_version": PIPELINE_VERSION,
        "pipeline": {
            **file_record(Path(__file__).resolve(), root),
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "pyarrow_version": __import__("pyarrow").__version__,
        },
        "formal_backtest_run_count": 0,
        "locked_test_open_count": 0,
        "inputs": [file_record(path, root) for path in input_files],
        "outputs": [file_record(path, root) for path in manifest_outputs],
        "row_counts": {
            "cleaned_price": len(price),
            "point_in_time_dividend_estimates": len(pit),
            "corporate_actions": len(actions),
            "cleaning_log": len(cleaning_log),
        },
        "audit": {
            "checks_total": len(checks),
            "errors": errors,
            "warnings": warnings,
            "pit_coverage": coverage,
            "stage5_internal_status": "PASS" if not errors else "FAIL",
            "stage4_closeout_status": "PASS" if not errors else "FAIL",
            "formal_l2_gate": "CLOSED_PENDING_INDEPENDENT_PRICE_CROSS_CHECK_AND_LATER_ACCOUNT_RECONCILIATION",
        },
    }
    output_paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "stage5_internal_status": manifest["audit"]["stage5_internal_status"],
        "stage4_closeout_status": manifest["audit"]["stage4_closeout_status"],
        "formal_l2_gate": manifest["audit"]["formal_l2_gate"],
        "checks": len(checks),
        "errors": len(errors),
        "coverage": coverage,
        "outputs": {key: str(path) for key, path in output_paths.items()},
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
