# -*- coding: utf-8 -*-
"""
MiniQMT 测试获取全市场财务数据（优化版）

优化点：
1. 自动探测 xtquant 路径，支持环境变量 QMT_SITE_PACKAGES。
2. 配置集中管理（输出目录、重试次数、节流间隔、处理上限、是否跳过已存在数据）。
3. 单只股票失败不影响整体，支持重试与失败列表落盘。
4. 支持断点续跑：目标目录已有 CSV 时可自动跳过。
5. 输出执行汇总（控制台 + summary.txt）。
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


# 你的本地 QMT 安装目录候选（可按需补充）
QMT_ROOT_CANDIDATES = [
    Path(r"C:\东莞证券QMT模拟交易端"),
    Path(r"C:\迅投极速策略交易系统交易终端\华泰证券QMT模拟"),
]


def resolve_qmt_site_packages() -> Path:
    env_path = os.environ.get("QMT_SITE_PACKAGES", "").strip()
    if env_path:
        p = Path(env_path)
        if (p / "xtquant").exists():
            return p

    for root in QMT_ROOT_CANDIDATES:
        p = root / "bin.x64" / "Lib" / "site-packages"
        if (p / "xtquant").exists():
            return p

    searched = [str(root / "bin.x64" / "Lib" / "site-packages") for root in QMT_ROOT_CANDIDATES]
    raise FileNotFoundError(
        "未找到 xtquant。请检查 QMT 安装路径，或设置环境变量 QMT_SITE_PACKAGES。\n"
        f"已尝试路径: {searched}"
    )


def ensure_xtdata():
    site_packages = resolve_qmt_site_packages()
    if str(site_packages) not in sys.path:
        sys.path.append(str(site_packages))

    from xtquant import xtdata  # type: ignore

    return xtdata


@dataclass
class FetchConfig:
    market_sector: str = "沪深京A股"
    output_dir: Path = Path("qmt_financial_data_ai")
    max_retries: int = 3
    retry_sleep_sec: float = 1.5
    per_stock_sleep_sec: float = 0.0
    progress_every: int = 10
    skip_if_exists: bool = True
    max_stocks: Optional[int] = None  # 调试可设为 10 等


@dataclass
class RunStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_all_stock_codes(xtdata, sector_name: str) -> List[str]:
    try:
        all_stocks = xtdata.get_stock_list_in_sector(sector_name) or []
        if not isinstance(all_stocks, list):
            raise TypeError(f"返回类型异常: {type(all_stocks)!r}")
        print(f"共获取到 {len(all_stocks)} 只股票（板块：{sector_name}）")
        return [x for x in all_stocks if x]
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        # 兜底列表，保证脚本可继续验证流程
        backup = [
            "000001.SZ", "000002.SZ", "600036.SH", "601318.SH",
            "600519.SH", "000858.SZ", "300750.SZ", "601888.SH",
        ]
        print(f"使用兜底股票列表，共 {len(backup)} 只")
        return backup


def has_existing_csv(stock_dir: Path) -> bool:
    return stock_dir.exists() and any(stock_dir.glob("*.csv"))


def download_financial_tables(
    xtdata,
    stock_code: str,
    max_retries: int,
    retry_sleep_sec: float,
) -> Optional[Dict[str, pd.DataFrame]]:
    for attempt in range(1, max_retries + 1):
        try:
            print(f"下载财务数据: {stock_code}（尝试 {attempt}/{max_retries}）")

            xtdata.download_financial_data2(stock_list=[stock_code])
            data = xtdata.get_financial_data(stock_list=[stock_code]) or {}

            if not isinstance(data, dict):
                raise TypeError(f"财务数据返回类型异常: {type(data)!r}")

            tables = data.get(stock_code)
            if isinstance(tables, dict) and tables:
                return tables

            print(f"[提示] {stock_code} 财务数据为空")
            return None

        except Exception as e:
            print(f"[警告] 下载失败: {stock_code}（第 {attempt} 次）错误: {e}")
            if attempt < max_retries:
                time.sleep(retry_sleep_sec)

    return None


def normalize_dataframe(df: Any) -> Optional[pd.DataFrame]:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df
    return None


def save_financial_tables(stock_code: str, tables: Dict[str, Any], output_dir: Path) -> Tuple[int, List[Path]]:
    stock_dir = output_dir / stock_code
    ensure_dir(stock_dir)

    saved_files: List[Path] = []
    saved_count = 0

    for table_name, raw_df in tables.items():
        try:
            df = normalize_dataframe(raw_df)
            if df is None:
                continue

            out_file = stock_dir / f"{table_name}.csv"
            df.to_csv(out_file, encoding="utf-8-sig", index=False)
            saved_files.append(out_file)
            saved_count += 1
        except Exception as e:
            print(f"[警告] 保存失败: {stock_code}/{table_name}，错误: {e}")

    return saved_count, saved_files


def table_latest_period(df: pd.DataFrame) -> str:
    if "m_timetag" not in df.columns or df.empty:
        return "N/A"
    value = df.iloc[-1]["m_timetag"]
    return str(value)


def print_stock_overview(stock_code: str, tables: Dict[str, Any], saved_count: int) -> None:
    print(f"{stock_code} 财务表概览：")
    printed = 0

    for table_name, raw_df in tables.items():
        df = normalize_dataframe(raw_df)
        if df is None:
            continue

        latest_period = table_latest_period(df)
        print(f"  - {table_name}: {len(df)} 行 x {len(df.columns)} 列，最新报告期: {latest_period}")
        printed += 1

    if printed == 0:
        print("  - 无可保存的非空表")

    print(f"  已保存文件数: {saved_count}")


def process_stock(xtdata, stock_code: str, cfg: FetchConfig) -> Tuple[str, int]:
    stock_dir = cfg.output_dir / stock_code

    if cfg.skip_if_exists and has_existing_csv(stock_dir):
        print(f"跳过已存在数据: {stock_code}")
        return "skipped", 0

    tables = download_financial_tables(
        xtdata=xtdata,
        stock_code=stock_code,
        max_retries=cfg.max_retries,
        retry_sleep_sec=cfg.retry_sleep_sec,
    )

    if not tables:
        return "failed", 0

    saved_count, _ = save_financial_tables(stock_code, tables, cfg.output_dir)
    print_stock_overview(stock_code, tables, saved_count)

    if cfg.per_stock_sleep_sec > 0:
        time.sleep(cfg.per_stock_sleep_sec)

    if saved_count > 0:
        return "success", saved_count
    return "failed", 0


def write_summary(
    output_dir: Path,
    stats: RunStats,
    failed_stocks: List[str],
    start_ts: float,
) -> Path:
    elapsed_sec = time.time() - start_ts
    summary_file = output_dir / "summary.txt"

    with summary_file.open("w", encoding="utf-8") as f:
        f.write("全市场财务数据抓取汇总\n")
        f.write("=" * 60 + "\n")
        f.write(f"总股票数: {stats.total}\n")
        f.write(f"成功: {stats.success}\n")
        f.write(f"失败: {stats.failed}\n")
        f.write(f"跳过: {stats.skipped}\n")
        f.write(f"总耗时: {elapsed_sec / 60:.2f} 分钟\n")

        if failed_stocks:
            f.write("\n失败股票列表:\n")
            for i, code in enumerate(failed_stocks, 1):
                f.write(f"{i}. {code}\n")

    return summary_file


def main() -> None:
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)

    cfg = FetchConfig()
    ensure_dir(cfg.output_dir)

    print("开始获取全市场财务数据（优化版）...")
    xtdata = ensure_xtdata()

    all_codes = get_all_stock_codes(xtdata, cfg.market_sector)
    if cfg.max_stocks is not None and cfg.max_stocks > 0:
        all_codes = all_codes[: cfg.max_stocks]
        print(f"已启用 max_stocks={cfg.max_stocks}，本次处理 {len(all_codes)} 只")

    stats = RunStats(total=len(all_codes))
    failed_stocks: List[str] = []

    start_ts = time.time()

    for idx, stock_code in enumerate(all_codes, 1):
        print("\n" + "=" * 60)
        print(f"进度: {idx}/{len(all_codes)} ({idx / max(1, len(all_codes)) * 100:.2f}%)")
        print(f"处理股票: {stock_code}")

        status, _ = process_stock(xtdata, stock_code, cfg)

        if status == "success":
            stats.success += 1
        elif status == "skipped":
            stats.skipped += 1
        else:
            stats.failed += 1
            failed_stocks.append(stock_code)

        if idx % cfg.progress_every == 0 or idx == len(all_codes):
            elapsed = time.time() - start_ts
            avg_per_stock = elapsed / idx
            remain = avg_per_stock * (len(all_codes) - idx)
            print("\n阶段汇总")
            print(f"  成功: {stats.success}")
            print(f"  失败: {stats.failed}")
            print(f"  跳过: {stats.skipped}")
            print(f"  已耗时: {elapsed / 60:.2f} 分钟")
            print(f"  预计剩余: {remain / 60:.2f} 分钟")

    summary_file = write_summary(cfg.output_dir, stats, failed_stocks, start_ts)

    total_elapsed = time.time() - start_ts
    print("\n" + "=" * 60)
    print("全市场财务数据获取完成")
    print("=" * 60)
    print(f"总股票数: {stats.total}")
    print(f"成功: {stats.success}")
    print(f"失败: {stats.failed}")
    print(f"跳过: {stats.skipped}")
    print(f"总耗时: {total_elapsed / 60:.2f} 分钟")
    print(f"输出目录: {cfg.output_dir}")
    print(f"汇总文件: {summary_file}")

    if failed_stocks:
        preview = failed_stocks[:20]
        print(f"失败股票（前 {len(preview)} 只）: {', '.join(preview)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断执行。")
    except Exception as e:
        print(f"\n程序执行出错: {e}")
