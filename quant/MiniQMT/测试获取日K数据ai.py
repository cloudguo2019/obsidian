# -*- coding: utf-8 -*-
"""
MiniQMT 测试获取日K数据（优化版）

优化点：
1. 自动探测 xtquant 路径，支持环境变量 QMT_SITE_PACKAGES。
2. 统一按日K（period='1d'）拉取并保存，修复原脚本周期不一致问题。
3. 输出目录改为脚本同级相对目录，避免硬编码盘符。
4. 支持跳过已存在文件、失败重试、阶段进度汇总。
5. 时间字段统一转换为 YYYY-MM-DD，便于后续分析。
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


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
class KlineConfig:
    sector_name: str = "沪深京A股"
    period: str = "1d"
    count: int = -1
    max_retries: int = 3
    retry_sleep_sec: float = 1.5
    per_stock_sleep_sec: float = 0.03
    progress_every: int = 50
    skip_if_exists: bool = True
    max_stocks: Optional[int] = None  # 调试时可设置为 20


@dataclass
class RunStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0


def timestamp_to_date_str(value) -> str:
    """将毫秒时间戳转换为 YYYY-MM-DD，异常时原样返回字符串。"""
    try:
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        return pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_all_stock_codes(xtdata, sector_name: str) -> List[str]:
    try:
        codes = xtdata.get_stock_list_in_sector(sector_name) or []
        if not isinstance(codes, list):
            raise TypeError(f"返回类型异常: {type(codes)!r}")
        return [c for c in codes if c]
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        # 兜底股票，确保流程可运行
        return ["000001.SZ", "000002.SZ", "600519.SH", "300750.SZ"]


def has_existing_file(out_dir: Path, stock_code: str) -> bool:
    return (out_dir / f"{stock_code}.csv").exists()


def fetch_kline_for_stock(
    xtdata,
    stock_code: str,
    period: str,
    count: int,
    max_retries: int,
    retry_sleep_sec: float,
) -> Optional[pd.DataFrame]:
    for attempt in range(1, max_retries + 1):
        try:
            data_map: Dict[str, pd.DataFrame] = xtdata.get_market_data_ex(
                count=count,
                stock_list=[stock_code],
                period=period,
            )
            if not isinstance(data_map, dict):
                raise TypeError(f"行情返回类型异常: {type(data_map)!r}")

            df = data_map.get(stock_code)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df

            print(f"[提示] {stock_code} 无{period}数据")
            return None

        except Exception as e:
            print(f"[警告] 获取失败: {stock_code}（第 {attempt}/{max_retries} 次）错误: {e}")
            if attempt < max_retries:
                time.sleep(retry_sleep_sec)

    return None


def normalize_kline_df(df: pd.DataFrame) -> pd.DataFrame:
    """标准化字段顺序并转换时间字段。"""
    data = df.copy()

    if "time" in data.columns:
        data["time"] = data["time"].map(timestamp_to_date_str)

    preferred = ["time", "open", "high", "low", "close", "volume", "amount"]
    cols = [c for c in preferred if c in data.columns] + [c for c in data.columns if c not in preferred]
    data = data[cols]

    return data


def save_kline_csv(df: pd.DataFrame, out_dir: Path, stock_code: str) -> Path:
    ensure_dir(out_dir)
    out_file = out_dir / f"{stock_code}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    return out_file


def process_stock(xtdata, stock_code: str, cfg: KlineConfig, out_dir: Path) -> str:
    if cfg.skip_if_exists and has_existing_file(out_dir, stock_code):
        print(f"跳过已存在: {stock_code}")
        return "skipped"

    df = fetch_kline_for_stock(
        xtdata=xtdata,
        stock_code=stock_code,
        period=cfg.period,
        count=cfg.count,
        max_retries=cfg.max_retries,
        retry_sleep_sec=cfg.retry_sleep_sec,
    )

    if df is None:
        return "failed"

    df2 = normalize_kline_df(df)
    out_file = save_kline_csv(df2, out_dir, stock_code)
    print(f"保存成功: {stock_code} -> {out_file.name}，共 {len(df2)} 条")

    if cfg.per_stock_sleep_sec > 0:
        time.sleep(cfg.per_stock_sleep_sec)

    return "success"


def write_summary(out_dir: Path, stats: RunStats, failed_codes: List[str], elapsed_sec: float) -> Path:
    summary = out_dir / "summary.txt"
    with summary.open("w", encoding="utf-8") as f:
        f.write("日K数据下载汇总\n")
        f.write("=" * 50 + "\n")
        f.write(f"总股票数: {stats.total}\n")
        f.write(f"成功: {stats.success}\n")
        f.write(f"失败: {stats.failed}\n")
        f.write(f"跳过: {stats.skipped}\n")
        f.write(f"总耗时: {elapsed_sec / 60:.2f} 分钟\n")

        if failed_codes:
            f.write("\n失败股票列表:\n")
            for i, code in enumerate(failed_codes, 1):
                f.write(f"{i}. {code}\n")

    return summary


def main() -> None:
    cfg = KlineConfig()

    base_dir = Path(__file__).resolve().parent
    out_dir = base_dir / "qmt_daily_k_data_ai"
    ensure_dir(out_dir)

    print("开始获取日K数据（优化版）...")
    xtdata = ensure_xtdata()

    all_codes = get_all_stock_codes(xtdata, cfg.sector_name)
    if cfg.max_stocks is not None and cfg.max_stocks > 0:
        all_codes = all_codes[: cfg.max_stocks]
        print(f"已启用 max_stocks={cfg.max_stocks}，本次处理 {len(all_codes)} 只")

    stats = RunStats(total=len(all_codes))
    failed_codes: List[str] = []

    start = time.time()

    print(f"共需处理股票数: {len(all_codes)}")
    for i, code in enumerate(all_codes, 1):
        print(f"\n处理进度: {i}/{len(all_codes)} -> {code}")
        status = process_stock(xtdata, code, cfg, out_dir)

        if status == "success":
            stats.success += 1
        elif status == "skipped":
            stats.skipped += 1
        else:
            stats.failed += 1
            failed_codes.append(code)

        if i % cfg.progress_every == 0 or i == len(all_codes):
            elapsed = time.time() - start
            avg = elapsed / max(i, 1)
            remain = avg * (len(all_codes) - i)
            print("阶段汇总:")
            print(f"  成功: {stats.success}")
            print(f"  失败: {stats.failed}")
            print(f"  跳过: {stats.skipped}")
            print(f"  已耗时: {elapsed / 60:.2f} 分钟")
            print(f"  预计剩余: {remain / 60:.2f} 分钟")

    elapsed = time.time() - start
    summary_path = write_summary(out_dir, stats, failed_codes, elapsed)

    print("\n日K数据处理完成")
    print(f"输出目录: {out_dir}")
    print(f"汇总文件: {summary_path}")
    print(f"总股票数: {stats.total}，成功: {stats.success}，失败: {stats.failed}，跳过: {stats.skipped}")

    if failed_codes:
        preview = failed_codes[:20]
        print(f"失败示例（前{len(preview)}只）: {', '.join(preview)}")


if __name__ == "__main__":
    try:
       main()
    except KeyboardInterrupt:
        print("\n用户中断执行。")
    except Exception as e:
        print(f"\n程序执行出错: {e}")
