#!/usr/bin/env python3
"""Fetch an independent AKShare/Sina unadjusted daily source and cross-check Xtquant.

This pipeline does not run any strategy logic.  The AKShare extract is archived as a
read-only source snapshot.  Standardized data and row-level differences are separate
derived outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd
import pyarrow


PIPELINE_VERSION = "HD-AKSHARE-PRICE-CROSSCHECK-1.0.0"
SYMBOL = "600900.SH"
AK_SYMBOL = "600900"
START_DATE = "20031118"
END_DATE = "20260909"
TIMEZONE = "Asia/Shanghai"
UPSTREAM_SOURCE = "sina"
AK_INTERFACE = "stock_zh_a_daily"
ADJUST = ""
PRICE_TOLERANCE_CNY = 0.005
MATERIAL_RELATIVE_DIFFERENCE = 0.01


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def normalize_akshare(raw: pd.DataFrame, raw_relative_path: str, fetched_at: str) -> pd.DataFrame:
    required = ["date", "open", "high", "low", "close", "volume", "amount", "outstanding_share", "turnover"]
    missing = [column for column in required if column not in raw.columns]
    assert_true(not missing, f"AKShare返回字段缺失: {missing}; 实际字段={raw.columns.tolist()}")
    out = raw.rename(columns={
        "date": "session_date",
        "volume": "volume_shares",
        "amount": "amount_cny",
        "turnover": "turnover_ratio",
    }).copy()
    out.insert(1, "source_symbol", "sh600900")
    out["session_date"] = pd.to_datetime(out["session_date"], errors="raise").dt.normalize()
    numeric = ["open", "high", "low", "close", "volume_shares", "amount_cny", "outstanding_share", "turnover_ratio"]
    for column in numeric:
        out[column] = pd.to_numeric(out[column], errors="raise")
    out.insert(1, "datetime", pd.to_datetime(out["session_date"].dt.strftime("%Y-%m-%d") + " 15:00:00").dt.tz_localize(TIMEZONE))
    out.insert(2, "timezone", TIMEZONE)
    out.insert(3, "symbol", SYMBOL)
    out.insert(4, "period", "1d")
    out.insert(5, "adjust", "none")
    out.insert(6, "source", "akshare")
    out.insert(7, "upstream_source", UPSTREAM_SOURCE)
    out.insert(8, "interface", AK_INTERFACE)
    out.insert(9, "source_version", f"akshare-{ak.__version__}-sina-bfq-cutoff-{END_DATE}")
    out.insert(10, "retrieved_at", fetched_at)
    out["volume_lots"] = out["volume_shares"] / 100.0
    out["raw_record_id"] = [f"{raw_relative_path}#L{line}" for line in range(2, len(out) + 2)]
    ordered = [
        "session_date", "datetime", "timezone", "symbol", "period", "adjust", "source", "upstream_source",
        "interface", "source_version", "retrieved_at", "source_symbol", "open", "high", "low", "close",
        "volume_shares", "volume_lots", "amount_cny", "outstanding_share", "turnover_ratio", "raw_record_id",
    ]
    return out[ordered].sort_values("session_date", kind="stable").reset_index(drop=True)


def build_comparison(ak_data: pd.DataFrame, xt_path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    xt = pd.read_csv(xt_path, low_memory=False)
    xt["session_date"] = pd.to_datetime(xt["datetime"], errors="raise").dt.normalize()
    xt = xt.rename(columns={
        "open": "xt_open", "high": "xt_high", "low": "xt_low", "close": "xt_close",
        "volume": "xt_volume_lots", "amount": "xt_amount_cny",
    })
    ak_for_merge = ak_data.rename(columns={
        "open": "ak_open", "high": "ak_high", "low": "ak_low", "close": "ak_close",
        "volume_lots": "ak_volume_lots", "amount_cny": "ak_amount_cny",
    })
    merged = xt[["session_date", "xt_open", "xt_high", "xt_low", "xt_close", "xt_volume_lots", "xt_amount_cny"]].merge(
        ak_for_merge[["session_date", "ak_open", "ak_high", "ak_low", "ak_close", "ak_volume_lots", "ak_amount_cny"]],
        on="session_date", how="outer", indicator=True, validate="one_to_one",
    ).sort_values("session_date", kind="stable").reset_index(drop=True)
    merged.insert(1, "symbol", SYMBOL)
    both = merged["_merge"].eq("both")
    abs_price_columns = []
    rel_price_columns = []
    for field in ["open", "high", "low", "close"]:
        abs_col = f"{field}_abs_diff_cny"
        rel_col = f"{field}_relative_diff"
        merged[abs_col] = (merged[f"xt_{field}"] - merged[f"ak_{field}"]).abs()
        denominator = merged[f"xt_{field}"].abs().replace(0, pd.NA)
        merged[rel_col] = merged[abs_col] / denominator
        abs_price_columns.append(abs_col)
        rel_price_columns.append(rel_col)
    merged["ohlc_max_abs_diff_cny"] = merged[abs_price_columns].max(axis=1)
    merged["ohlc_max_relative_diff"] = merged[rel_price_columns].max(axis=1)
    merged["ohlc_all_equal_to_cent"] = both & merged["ohlc_max_abs_diff_cny"].le(PRICE_TOLERANCE_CNY)
    merged["material_price_difference_over_1pct"] = both & merged["ohlc_max_relative_diff"].gt(MATERIAL_RELATIVE_DIFFERENCE)
    merged["volume_abs_diff_lots"] = (merged["xt_volume_lots"] - merged["ak_volume_lots"]).abs()
    merged["volume_relative_diff"] = merged["volume_abs_diff_lots"] / merged["xt_volume_lots"].abs().replace(0, pd.NA)
    merged["amount_abs_diff_cny"] = (merged["xt_amount_cny"] - merged["ak_amount_cny"]).abs()
    merged["amount_relative_diff"] = merged["amount_abs_diff_cny"] / merged["xt_amount_cny"].abs().replace(0, pd.NA)
    merged["row_result"] = "MATCH"
    merged.loc[~both, "row_result"] = "MISSING_ONE_SOURCE"
    merged.loc[both & ~merged["ohlc_all_equal_to_cent"], "row_result"] = "PRICE_DIFFERENCE"
    merged.loc[merged["material_price_difference_over_1pct"], "row_result"] = "MATERIAL_PRICE_DIFFERENCE"

    overlap = merged.loc[both]
    statistics = {
        "xtquant_rows": int(len(xt)),
        "akshare_rows": int(len(ak_data)),
        "overlap_rows": int(both.sum()),
        "xtquant_only_rows": int(merged["_merge"].eq("left_only").sum()),
        "akshare_only_rows": int(merged["_merge"].eq("right_only").sum()),
        "ohlc_equal_to_cent_rows": int(overlap["ohlc_all_equal_to_cent"].sum()),
        "ohlc_price_difference_rows": int((~overlap["ohlc_all_equal_to_cent"]).sum()),
        "material_price_difference_over_1pct_rows": int(overlap["material_price_difference_over_1pct"].sum()),
        "maximum_ohlc_absolute_difference_cny": float(overlap["ohlc_max_abs_diff_cny"].max()),
        "maximum_ohlc_relative_difference": float(overlap["ohlc_max_relative_diff"].max()),
        "volume_exact_match_rows": int(overlap["volume_abs_diff_lots"].eq(0).sum()),
        "volume_difference_rows": int(overlap["volume_abs_diff_lots"].gt(0).sum()),
        "maximum_volume_absolute_difference_lots": float(overlap["volume_abs_diff_lots"].max()),
        "maximum_volume_relative_difference": float(overlap["volume_relative_diff"].max()),
        "amount_exact_match_rows": int(overlap["amount_abs_diff_cny"].eq(0).sum()),
        "amount_difference_rows": int(overlap["amount_abs_diff_cny"].gt(0).sum()),
        "maximum_amount_absolute_difference_cny": float(overlap["amount_abs_diff_cny"].max()),
        "maximum_amount_relative_difference": float(overlap["amount_relative_diff"].max()),
        "first_date": merged["session_date"].min().date().isoformat(),
        "last_date": merged["session_date"].max().date().isoformat(),
    }
    return merged, statistics


def report_text(fetched_at: str, stats: dict[str, object], checks: dict[str, bool]) -> str:
    return f"""# 600900.SH AkShare未复权日线独立副源核验

> [已观察事实｜A] 获取时间：{fetched_at}；数据截止：2026-09-09；Python {platform.python_version()}；AKShare {ak.__version__}；接口`stock_zh_a_daily`；参数`adjust=\"\"`。

## 1. 研究问题

[方法选择｜C] 使用AKShare调用新浪财经日频历史行情作为独立于Xtquant的副源，逐日核验600900.SH未复权OHLC、成交量和成交额，不替换Xtquant主数据。原计划的东方财富接口连续两次发生代理连接中断且未写出数据，因此显式改用同属AKShare官方文档的新浪接口。

## 2. 来源和口径

[已观察事实｜A] AKShare官方文档说明`stock_zh_a_daily`的上游为新浪财经，`adjust=\"\"`返回不复权数据；成交量单位为股、成交额单位为元。标准化表另以`volume_lots = volume_shares / 100`转换为手，以便与Xtquant比较。

[方法选择｜C] 主源为Xtquant未复权日线，副源为AKShare/Sina未复权日线。价格以0.005元为分币等价容差；相对差异超过1%视为重大差异并阻止价格双源门禁通过。

## 3. 数据覆盖

[计算结果｜A] Xtquant {stats['xtquant_rows']:,}行，AKShare {stats['akshare_rows']:,}行，共同日期{stats['overlap_rows']:,}行；仅Xtquant {stats['xtquant_only_rows']}行，仅AKShare {stats['akshare_only_rows']}行；共同范围{stats['first_date']}至{stats['last_date']}。

## 4. 价格核验

[计算结果｜A] OHLC按0.005元容差一致{stats['ohlc_equal_to_cent_rows']:,}/{stats['overlap_rows']:,}行；存在价格差异{stats['ohlc_price_difference_rows']}行；超过1%重大价格差异{stats['material_price_difference_over_1pct_rows']}行。

[计算结果｜A] 最大OHLC绝对差异为{stats['maximum_ohlc_absolute_difference_cny']:.10f}元，最大相对差异为{stats['maximum_ohlc_relative_difference']:.10%}。

## 5. 成交量和成交额核验

[计算结果｜A] 成交量完全相同{stats['volume_exact_match_rows']:,}行，存在差异{stats['volume_difference_rows']:,}行；最大绝对差异{stats['maximum_volume_absolute_difference_lots']:,.0f}手，最大相对差异{stats['maximum_volume_relative_difference']:.10%}。

[计算结果｜A] 成交额完全相同{stats['amount_exact_match_rows']:,}行，存在差异{stats['amount_difference_rows']:,}行；最大绝对差异{stats['maximum_amount_absolute_difference_cny']:,.2f}元，最大相对差异{stats['maximum_amount_relative_difference']:.10%}。

## 6. 数据质量检查

| 检查 | 结果 |
|---|---|
| [计算结果｜A] AKShare记录唯一 | {'PASS' if checks['ak_unique'] else 'FAIL'} |
| [计算结果｜A] AKShare OHLC约束 | {'PASS' if checks['ak_ohlc'] else 'FAIL'} |
| [计算结果｜A] AKShare价格为正 | {'PASS' if checks['ak_positive'] else 'FAIL'} |
| [计算结果｜A] 日期覆盖一致 | {'PASS' if checks['same_dates'] else 'FAIL'} |
| [计算结果｜A] 无超过1%价格差异 | {'PASS' if checks['no_material_price_difference'] else 'FAIL'} |

## 7. 发现的问题和证据等级

[已观察事实｜B] AKShare是取数库，实际价格上游是新浪财经；因此证据链写作“AkShare/Sina”，不能把AkShare误写成交易所原始行情源。

[已知限制｜B] 成交量或成交额的微小差异可能来自供应商取整、修订或单位转换；逐日差异已完整保留，不用价格一致性掩盖非价格字段差异。

[已知限制｜B] 两个供应商都可能接收交易所同一基础行情，因此双源一致能显著降低单文件损坏或复权口径错误风险，但不能证明交易所原始逐笔记录绝对无误。

## 8. 结论

[计算结果｜A] 独立价格副源门禁：`{'PASS' if all(checks.values()) else 'FAIL'}`。该结论只支持数据交叉核验，不是策略收益证据。

## 9. 是否允许继续

[方法选择｜C] 若本报告全部检查通过，则阶段5的独立价格缺口关闭；仍须按阶段顺序完成样本划分和公平基准，且不因本次数据核验自动授权正式回测或打开锁定集。
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--xtquant", type=Path, default=Path("research/QMTData/data/market_kline/csv/1d/none/600900.SH.csv"))
    args = parser.parse_args()
    root = args.root.resolve()
    xt_path = args.xtquant if args.xtquant.is_absolute() else root / args.xtquant
    raw_dir = root / "research/topics/high_dividend_bond/datasets/raw/akshare"
    derived_dir = root / "research/topics/high_dividend_bond/datasets/derived"
    raw_dir.mkdir(parents=True, exist_ok=True)
    derived_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "600900_akshare_stock_zh_a_daily_sina_bfq_20031118_20260909.csv"
    normalized_csv = derived_dir / "600900_akshare_daily_unadjusted_v1.csv"
    normalized_parquet = derived_dir / "600900_akshare_daily_unadjusted_v1.parquet"
    comparison_csv = derived_dir / "600900_xtquant_akshare_price_crosscheck_v1.csv"
    report_path = root / "research/topics/high_dividend_bond/datasets/akshare_price_crosscheck_2026-09-10.md"
    manifest_path = root / "research/topics/high_dividend_bond/datasets/akshare_price_source_manifest_v1.json"

    if raw_path.exists():
        raise FileExistsError(f"原始副源快照已存在，拒绝覆盖: {raw_path}")
    fetched_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    raw = ak.stock_zh_a_daily(
        symbol=f"sh{AK_SYMBOL}", start_date=START_DATE, end_date=END_DATE, adjust=ADJUST
    )
    assert_true(not raw.empty, "AKShare返回空表")
    raw_relative = raw_path.relative_to(root).as_posix()
    normalized = normalize_akshare(raw, raw_relative, fetched_at)
    assert_true(normalized["source_symbol"].eq("sh600900").all(), "AKShare证券代码不一致")
    assert_true(not normalized.duplicated(["symbol", "session_date"]).any(), "AKShare日期重复")
    assert_true(normalized["session_date"].is_monotonic_increasing, "AKShare日期未排序")
    ak_ohlc = (
        (normalized["low"] <= normalized["open"])
        & (normalized["open"] <= normalized["high"])
        & (normalized["low"] <= normalized["close"])
        & (normalized["close"] <= normalized["high"])
    ).all()
    ak_positive = normalized[["open", "high", "low", "close"]].gt(0).all(axis=1).all()
    assert_true(bool(ak_ohlc), "AKShare OHLC约束失败")
    assert_true(bool(ak_positive), "AKShare价格非正")
    comparison, stats = build_comparison(normalized, xt_path)
    checks = {
        "ak_unique": not normalized.duplicated(["symbol", "session_date"]).any(),
        "ak_ohlc": bool(ak_ohlc),
        "ak_positive": bool(ak_positive),
        "same_dates": stats["xtquant_only_rows"] == 0 and stats["akshare_only_rows"] == 0,
        "no_material_price_difference": stats["material_price_difference_over_1pct_rows"] == 0,
    }

    raw.to_csv(raw_path, index=False, encoding="utf-8-sig")
    normalized.to_csv(normalized_csv, index=False, encoding="utf-8-sig", date_format="%Y-%m-%dT%H:%M:%S%z")
    normalized.to_parquet(normalized_parquet, index=False, engine="pyarrow")
    comparison.to_csv(comparison_csv, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    report_path.write_text(report_text(fetched_at, stats, checks), encoding="utf-8")
    os.chmod(raw_path, stat.S_IREAD)

    outputs = [raw_path, normalized_csv, normalized_parquet, comparison_csv, report_path]
    manifest = {
        "statement_type": "计算结果",
        "manifest_version": "HD-AKSHARE-PRICE-SOURCE-MANIFEST-1.0",
        "generated_at": fetched_at,
        "timezone": TIMEZONE,
        "source": {
            "library": "AKShare",
            "library_version": ak.__version__,
            "interface": AK_INTERFACE,
            "upstream_source": UPSTREAM_SOURCE,
            "symbol": AK_SYMBOL,
            "period": "daily",
            "start_date": START_DATE,
            "end_date": END_DATE,
            "adjust_parameter": ADJUST,
            "adjust_meaning": "unadjusted",
            "documentation": "https://akshare.akfamily.xyz/data/stock/stock.html",
        },
        "runtime": {
            "python_version": platform.python_version(),
            "python_executable": "C:/Users/cg/AppData/Local/venvs/high-dividend-bond-py311/Scripts/python.exe",
            "pandas_version": pd.__version__,
            "pyarrow_version": pyarrow.__version__,
            "pipeline_version": PIPELINE_VERSION,
            **record(Path(__file__).resolve(), root),
        },
        "inputs": [record(xt_path, root)],
        "outputs": [record(path, root) for path in outputs],
        "statistics": stats,
        "checks": checks,
        "independent_price_gate": "PASS" if all(checks.values()) else "FAIL",
        "formal_backtest_run_count": 0,
        "locked_test_open_count": 0,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "independent_price_gate": manifest["independent_price_gate"],
        "statistics": stats,
        "checks": checks,
        "outputs": [str(path) for path in outputs + [manifest_path]],
    }, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
