# encoding: utf-8
"""
MiniQMT 测试获取股票价格脚本（优化版）

保留原始 `测试获取a股股票价格.py` 不变，本文件提供更稳健的行情查询逻辑：
1. 将 QMT 路径、板块名、测试股票等配置集中管理，便于后续复用。
2. 为股票列表获取、tick 查询、涨跌统计分别封装函数，结构更清晰。
3. 增加空结果、异常数据、接口异常的保护，避免脚本直接中断。
4. 默认打印精简摘要，同时支持查看指定股票的最新价明细。
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


QMT_ROOT_CANDIDATES = [
    Path(r"C:\东莞证券QMT模拟交易端"),
    Path(r"C:\迅投极速策略交易系统交易终端 华泰证券QMT模拟"),
]


def resolve_qmt_site_packages() -> Path:
    for qmt_root in QMT_ROOT_CANDIDATES:
        site_packages = qmt_root / "bin.x64" / "Lib" / "site-packages"
        xtquant_path = site_packages / "xtquant"
        if xtquant_path.exists():
            return site_packages

    searched_paths = [
        str(qmt_root / "bin.x64" / "Lib" / "site-packages")
        for qmt_root in QMT_ROOT_CANDIDATES
    ]
    raise FileNotFoundError(
        "未找到 xtquant 库，请检查 QMT 安装目录。已搜索路径: "
        + " ; ".join(searched_paths)
    )


QMT_SITE_PACKAGES = resolve_qmt_site_packages()

if str(QMT_SITE_PACKAGES) not in sys.path:
    sys.path.append(str(QMT_SITE_PACKAGES))


from xtquant import xtdata


DEFAULT_SECTOR_NAME = "沪深京A股"
DEFAULT_TEST_SYMBOLS = ["000001.SZ", "600519.SH", "159919.SZ"]


@dataclass
class MarketStats:
    total: int = 0
    queried: int = 0
    up: int = 0
    down: int = 0
    unchanged: int = 0
    invalid: int = 0
    missing: int = 0

    @property
    def valid(self) -> int:
        return self.up + self.down + self.unchanged


@dataclass
class QuoteSnapshot:
    stock_code: str
    last_price: float = 0.0
    pre_close: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    change_amount: float = 0.0
    change_pct: float = 0.0
    bid1_price: float = 0.0
    ask1_price: float = 0.0


@dataclass
class MarketAnalyzer:
    sector_name: str = DEFAULT_SECTOR_NAME
    test_symbols: List[str] = field(default_factory=lambda: DEFAULT_TEST_SYMBOLS.copy())

    def get_all_stock_codes(self) -> List[str]:
        try:
            stock_codes = xtdata.get_stock_list_in_sector(self.sector_name) or []
        except Exception as exc:
            raise RuntimeError(f"获取板块股票列表失败: sector={self.sector_name}, error={exc}") from exc

        if not isinstance(stock_codes, list):
            raise RuntimeError(f"股票列表返回格式异常: {type(stock_codes)!r}")

        return stock_codes

    def get_full_tick(self, stock_codes: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        stock_code_list = [code for code in stock_codes if code]
        if not stock_code_list:
            return {}

        try:
            quotes = xtdata.get_full_tick(stock_code_list) or {}
        except Exception as exc:
            raise RuntimeError(f"获取实时行情失败: error={exc}") from exc

        if not isinstance(quotes, dict):
            raise RuntimeError(f"实时行情返回格式异常: {type(quotes)!r}")

        return quotes

    def get_market_stats(self) -> Tuple[MarketStats, Dict[str, Dict[str, Any]]]:
        stock_codes = self.get_all_stock_codes()
        quotes = self.get_full_tick(stock_codes)
        stats = MarketStats(total=len(stock_codes), queried=len(quotes))

        for stock_code in stock_codes:
            quote = quotes.get(stock_code)
            if quote is None:
                stats.missing += 1
                continue

            last_price = safe_float(quote.get("lastPrice"))
            pre_close = safe_float(quote.get("lastClose"))

            if last_price <= 0 or pre_close <= 0:
                stats.invalid += 1
                continue

            change_pct = (last_price - pre_close) / pre_close * 100
            if change_pct > 1e-6:
                stats.up += 1
            elif change_pct < -1e-6:
                stats.down += 1
            else:
                stats.unchanged += 1

        return stats, quotes

    def build_snapshot(self, stock_code: str, quote: Optional[Dict[str, Any]]) -> Optional[QuoteSnapshot]:
        if not quote:
            return None

        last_price = safe_float(quote.get("lastPrice"))
        pre_close = safe_float(quote.get("lastClose"))
        open_price = safe_float(quote.get("open"))
        high_price = safe_float(quote.get("high"))
        low_price = safe_float(quote.get("low"))
        volume = safe_float(quote.get("volume"))
        amount = safe_float(quote.get("amount"))
        bid1_price = first_price(quote.get("bidPrice"))
        ask1_price = first_price(quote.get("askPrice"))

        change_amount = last_price - pre_close if pre_close > 0 else 0.0
        change_pct = change_amount / pre_close * 100 if pre_close > 0 else 0.0

        return QuoteSnapshot(
            stock_code=stock_code,
            last_price=last_price,
            pre_close=pre_close,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            volume=volume,
            amount=amount,
            change_amount=change_amount,
            change_pct=change_pct,
            bid1_price=bid1_price,
            ask1_price=ask1_price,
        )

    def print_market_summary(self, stats: MarketStats) -> None:
        print("=== 实时涨跌统计 ===")
        print(f"板块: {self.sector_name}")
        print(f"股票总数: {stats.total}")
        print(f"成功返回行情数: {stats.queried}")
        print(f"上涨: {stats.up}")
        print(f"下跌: {stats.down}")
        print(f"平盘: {stats.unchanged}")
        print(f"无效数据: {stats.invalid}")
        print(f"缺失行情: {stats.missing}")

        if stats.valid > 0:
            up_ratio = stats.up / stats.valid * 100
            down_ratio = stats.down / stats.valid * 100
            print(f"上涨占比: {up_ratio:.2f}%")
            print(f"下跌占比: {down_ratio:.2f}%")

    def print_symbol_snapshots(self, quotes: Dict[str, Dict[str, Any]]) -> None:
        if not self.test_symbols:
            return

        print("\n=== 指定股票价格明细 ===")
        for stock_code in self.test_symbols:
            snapshot = self.build_snapshot(stock_code, quotes.get(stock_code))
            if snapshot is None:
                print(f"{stock_code}: 未获取到行情数据")
                continue

            print(
                f"{snapshot.stock_code} "
                f"最新价={snapshot.last_price:.3f}, "
                f"昨收={snapshot.pre_close:.3f}, "
                f"涨跌额={snapshot.change_amount:.3f}, "
                f"涨跌幅={snapshot.change_pct:.2f}%, "
                f"开盘={snapshot.open_price:.3f}, "
                f"最高={snapshot.high_price:.3f}, "
                f"最低={snapshot.low_price:.3f}, "
                f"买一={snapshot.bid1_price:.3f}, "
                f"卖一={snapshot.ask1_price:.3f}"
            )

    def run(self) -> None:
        stats, quotes = self.get_market_stats()
        self.print_market_summary(stats)
        self.print_symbol_snapshots(quotes)


def first_price(values: Any) -> float:
    if not isinstance(values, list) or not values:
        return 0.0
    return safe_float(values[0])


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    analyzer = MarketAnalyzer()
    try:
        analyzer.run()
    except Exception as exc:
        print(f"脚本执行失败: {exc}")


if __name__ == "__main__":
    main()
