# -*- coding: utf-8 -*-
"""
MiniQMT 测试获取行业板块成分股（优化版）

说明：
1. 自动探测 xtquant 安装路径，也支持通过环境变量 QMT_SITE_PACKAGES 指定。
2. 结构化拆分：下载板块、收集成分股、补全股票名称、保存结果、打印统计。
3. 增强容错：单板块失败不中断全流程，名称查询失败会降级为“未知”。
4. 提供清晰进度输出，便于长时间任务观察。
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


# 根据你的环境补充/调整候选安装目录
QMT_ROOT_CANDIDATES = [
    Path(r"C:\东莞证券QMT模拟交易端"),
    Path(r"C:\迅投极速策略交易系统交易终端\华泰证券QMT模拟"),
]


def resolve_qmt_site_packages() -> Path:
    """自动定位 xtquant 所在的 site-packages 目录。"""
    env_path = os.environ.get("QMT_SITE_PACKAGES", "").strip()
    if env_path:
        p = Path(env_path)
        if (p / "xtquant").exists():
            return p

    for root in QMT_ROOT_CANDIDATES:
        p = root / "bin.x64" / "Lib" / "site-packages"
        if (p / "xtquant").exists():
            return p

    searched = [str(r / "bin.x64" / "Lib" / "site-packages") for r in QMT_ROOT_CANDIDATES]
    raise FileNotFoundError(
        "未找到 xtquant。请检查 QMT 安装路径，或设置环境变量 QMT_SITE_PACKAGES。\n"
        f"已尝试路径: {searched}"
    )


def ensure_xtdata():
    """确保可导入 xtquant.xtdata。"""
    site_packages = resolve_qmt_site_packages()
    if str(site_packages) not in sys.path:
        sys.path.append(str(site_packages))

    from xtquant import xtdata  # type: ignore

    return xtdata


@dataclass
class StockInfo:
    code: str
    name: str = ""
    industries: Set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.industries is None:
            self.industries = set()


def save_sectors_to_file(sectors: Iterable[str], filename: Path) -> None:
    sectors_sorted = sorted(set(s for s in sectors if s))
    with filename.open("w", encoding="utf-8") as f:
        f.write("QMT 行业/概念板块列表\n")
        f.write("=" * 60 + "\n")
        f.write(f"共 {len(sectors_sorted)} 个板块\n\n")
        for i, sector in enumerate(sectors_sorted, 1):
            f.write(f"{i:4d}. {sector}\n")

    print(f"板块列表已保存: {filename}")


def save_stock_table(stocks: Dict[str, StockInfo], filename: Path) -> None:
    with filename.open("w", encoding="utf-8") as f:
        f.write("代码\t名称\t所属行业板块\n")
        f.write("-" * 120 + "\n")
        for code in sorted(stocks.keys()):
            info = stocks[code]
            industries_str = ", ".join(sorted(info.industries))
            f.write(f"{info.code}\t{info.name or '未知'}\t{industries_str}\n")

    print(f"股票总表已保存: {filename}（共 {len(stocks)} 只）")


def save_by_industry(stocks: Dict[str, StockInfo], filename: Path) -> None:
    industry_to_stocks: Dict[str, List[StockInfo]] = {}

    for info in stocks.values():
        for industry in info.industries:
            industry_to_stocks.setdefault(industry, []).append(info)

    with filename.open("w", encoding="utf-8") as f:
        f.write("按行业/板块分组的成分股列表\n")
        f.write("=" * 120 + "\n\n")

        for industry in sorted(industry_to_stocks.keys()):
            group = sorted(industry_to_stocks[industry], key=lambda x: x.code)
            f.write(f"{industry}:\n")
            for info in group:
                f.write(f"  {info.code}\t{info.name or '未知'}\n")
            f.write(f"  共 {len(group)} 只\n\n")

    print(f"按行业分组文件已保存: {filename}")


def collect_stocks_with_industries(xtdata, sectors: List[str], pause: float = 0.005) -> Dict[str, StockInfo]:
    """遍历板块，收集股票代码与所属板块（去重）。"""
    all_stocks: Dict[str, StockInfo] = {}

    total = len(sectors)
    for idx, sector in enumerate(sectors, 1):
        try:
            members = xtdata.get_stock_list_in_sector(sector) or []
        except Exception as exc:
            print(f"[警告] 板块处理失败: {sector}，错误: {exc}")
            continue

        for code in members:
            info = all_stocks.get(code)
            if info is None:
                info = StockInfo(code=code)
                all_stocks[code] = info
            info.industries.add(sector)

        if idx % 20 == 0 or idx == total:
            print(f"板块进度: {idx}/{total}，当前板块 {sector}，累计股票 {len(all_stocks)}")

        if pause > 0:
            time.sleep(pause)

    return all_stocks


def fill_stock_names(xtdata, all_stocks: Dict[str, StockInfo], pause: float = 0.0) -> None:
    """批量补全股票名称。"""
    codes = sorted(all_stocks.keys())
    total = len(codes)

    for idx, code in enumerate(codes, 1):
        try:
            detail: Optional[Dict[str, Any]] = xtdata.get_instrument_detail(code)
            name = (detail or {}).get("InstrumentName", "")
            all_stocks[code].name = str(name).strip() or "未知"
        except Exception as exc:
            all_stocks[code].name = "未知"
            print(f"[警告] 股票名称获取失败: {code}，错误: {exc}")

        if idx % 200 == 0 or idx == total:
            print(f"名称进度: {idx}/{total}")

        if pause > 0:
            time.sleep(pause)


def print_stats(stocks: Dict[str, StockInfo]) -> None:
    total = len(stocks)
    if total == 0:
        print("未获取到任何股票数据。")
        return

    industry_counts = [len(x.industries) for x in stocks.values()]
    avg_industries = sum(industry_counts) / total
    max_industries = max(industry_counts)
    min_industries = min(industry_counts)

    unknown_name_count = sum(1 for x in stocks.values() if (x.name or "") == "未知")

    print("\n统计信息")
    print("-" * 40)
    print(f"总股票数: {total}")
    print(f"名称缺失数: {unknown_name_count}")
    print(f"平均每只股票所属板块数: {avg_industries:.2f}")
    print(f"最少所属板块数: {min_industries}")
    print(f"最多所属板块数: {max_industries}")

    print("\n示例（前 10 只）")
    print("-" * 40)
    for code in sorted(stocks.keys())[:10]:
        info = stocks[code]
        industries_preview = ", ".join(sorted(info.industries)[:3])
        if len(info.industries) > 3:
            industries_preview += f" ... 等{len(info.industries)}个"
        print(f"{info.code}\t{info.name or '未知'}\t{industries_preview}")


def main() -> None:
    print("开始执行：获取行业/板块成分股")
    xtdata = ensure_xtdata()

    # 输出到当前脚本目录
    base_dir = Path(__file__).resolve().parent
    sectors_file = base_dir / "qmt_概念板块ai.txt"
    all_stocks_file = base_dir / "all_stocks_industry_info_ai.txt"
    grouped_file = base_dir / "stocks_grouped_by_industry_ai.txt"

    print("正在下载板块数据...")
    xtdata.download_sector_data()

    sectors = xtdata.get_sector_list() or []
    sectors = [s for s in sectors if s]
    print(f"获取到板块数量: {len(sectors)}")

    if not sectors:
        print("未获取到板块列表，任务结束。")
        return

    save_sectors_to_file(sectors, sectors_file)

    print("正在汇总成分股...")
    all_stocks = collect_stocks_with_industries(xtdata, sectors, pause=0.005)
    print(f"已汇总股票数: {len(all_stocks)}")

    print("正在补全股票名称...")
    fill_stock_names(xtdata, all_stocks, pause=0.0)

    save_stock_table(all_stocks, all_stocks_file)
    save_by_industry(all_stocks, grouped_file)
    print_stats(all_stocks)

    print("\n任务完成。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"脚本执行失败: {e}")
