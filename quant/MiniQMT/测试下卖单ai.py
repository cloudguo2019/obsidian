# encoding: utf-8
"""
MiniQMT 测试卖单脚本（优化版）

保留原始 `测试下卖单.py` 不变，本文件提供更稳健的卖出测试逻辑：
1. 先配置 sys.path，再导入 xtquant，避免导入失败。
2. 拆分连接、查资产、查持仓、取行情、生成卖单计划、执行卖单等步骤。
3. 对连接失败、资产为空、持仓不足、行情缺失、价格无效做保护。
4. 卖出价格优先使用买一价，必要时回退到卖一价、最新价、跌停价。
5. 使用 finally 关闭连接，避免异常退出后资源未释放。
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


QMT_ROOT = Path(r"C:\东莞证券QMT模拟交易端")
QMT_SITE_PACKAGES = QMT_ROOT / "bin.x64" / "Lib" / "site-packages"
QMT_USERDATA_DIR = QMT_ROOT / "userdata_mini"

if str(QMT_SITE_PACKAGES) not in sys.path:
    sys.path.append(str(QMT_SITE_PACKAGES))


from xtquant import xtconstant, xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount


ACCOUNT_ID = "2038046457"
ACCOUNT_TYPE = "STOCK"
SESSION_ID = int(time.time())
TEST_SYMBOLS = ["600875.SH"]
SELL_VOLUME = 100


@dataclass
class SellOrderPlan:
    stock_code: str
    order_type: int
    order_volume: int
    price_type: int
    order_price: float


class MyStrategy(XtQuantTraderCallback):
    def __init__(
        self,
        account_id: str = ACCOUNT_ID,
        symbols: Optional[List[str]] = None,
        sell_volume: int = SELL_VOLUME,
    ) -> None:
        super().__init__()
        self.account_id = account_id
        self.account = StockAccount(account_id, ACCOUNT_TYPE)
        self.symbols = symbols or TEST_SYMBOLS.copy()
        self.sell_volume = sell_volume
        self.trader = XtQuantTrader(str(QMT_USERDATA_DIR), SESSION_ID)
        self.connected = False

    def start(self) -> None:
        self.trader.register_callback(self)
        self.trader.start()

        connect_result = self.trader.connect()
        self.connected = connect_result == 0
        print(f"connect_result: {connect_result}")

        if not self.connected:
            raise RuntimeError("连接 QMT 失败，请确认客户端已启动、已登录且路径配置正确。")

        print("连接正常")

    def stop(self) -> None:
        if self.connected:
            self.trader.stop()
            self.connected = False
            print("交易连接已关闭")

    def query_account_asset(self) -> Any:
        account_res = self.trader.query_stock_asset(self.account)
        print("account_res:", account_res)

        if account_res is None:
            raise RuntimeError("账户资产查询失败，返回结果为空。")

        cash = safe_float(getattr(account_res, "cash", 0))
        print(f"可用余额: {cash:.2f}")
        return account_res

    def query_position(self, stock_code: str) -> Any:
        try:
            position = self.trader.query_stock_position(self.account, stock_code)
        except Exception as exc:
            raise RuntimeError(f"查询持仓失败: {stock_code}, {exc}") from exc

        print(f"position[{stock_code}]:", position)
        return position

    def fetch_ticks(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        if not symbols:
            return {}

        stock_info = xtdata.get_full_tick(symbols) or {}
        print(f"成功获取 {len(stock_info)} / {len(symbols)} 只股票的 tick 数据")
        return stock_info

    def build_sell_plan(
        self,
        stock_code: str,
        tick: Dict[str, Any],
        available_volume: int,
    ) -> Optional[SellOrderPlan]:
        if self.sell_volume <= 0 or self.sell_volume % 100 != 0:
            raise ValueError("卖出数量必须为正整数，且 A 股需为 100 股的整数倍。")

        if available_volume <= 0:
            print(f"{stock_code} 当前无可卖数量，跳过。")
            return None

        if available_volume < self.sell_volume:
            print(
                f"{stock_code} 可卖数量不足，计划卖出 {self.sell_volume} 股，"
                f"当前仅可卖 {available_volume} 股。"
            )
            return None

        detail = xtdata.get_instrument_detail(stock_code) or {}
        last_price = safe_float(tick.get("lastPrice", 0))
        bid_prices = ensure_float_list(tick.get("bidPrice"))
        ask_prices = ensure_float_list(tick.get("askPrice"))
        up_stop_price = safe_float(detail.get("UpStopPrice", 0))
        down_stop_price = safe_float(detail.get("DownStopPrice", 0))

        order_price = self.select_sell_price(bid_prices, ask_prices, last_price, down_stop_price)
        if order_price <= 0:
            print(f"{stock_code} 卖出价格无效，跳过。")
            return None

        print(
            f"stock={stock_code} last={last_price:.3f} "
            f"buy1={first_or_zero(bid_prices):.3f} "
            f"sell1={first_or_zero(ask_prices):.3f} "
            f"涨停={up_stop_price:.3f} 跌停={down_stop_price:.3f}"
        )
        print(
            f"计划卖出: stock={stock_code}, volume={self.sell_volume}, "
            f"price={order_price:.3f}, expected_amount={order_price * self.sell_volume:.2f}"
        )

        return SellOrderPlan(
            stock_code=stock_code,
            order_type=xtconstant.STOCK_SELL,
            order_volume=self.sell_volume,
            price_type=xtconstant.FIX_PRICE,
            order_price=order_price,
        )

    def select_sell_price(
        self,
        bid_prices: List[float],
        ask_prices: List[float],
        last_price: float,
        down_stop_price: float,
    ) -> float:
        for price in bid_prices:
            if price > 0:
                return round(price, 3)

        for price in ask_prices:
            if price > 0:
                return round(price, 3)

        if last_price > 0:
            return round(last_price, 3)

        if down_stop_price > 0:
            return round(down_stop_price, 3)

        return 0.0

    def place_order(self, plan: SellOrderPlan) -> int:
        order_id = self.trader.order_stock(
            self.account,
            plan.stock_code,
            plan.order_type,
            plan.order_volume,
            plan.price_type,
            plan.order_price,
            strategy_name="测试卖单",
        )

        if order_id <= 0:
            raise RuntimeError(f"{plan.stock_code} 卖单提交失败，返回 order_id={order_id}")

        print(
            f"下单成功: order_id={order_id}, stock={plan.stock_code}, "
            f"volume={plan.order_volume}, price={plan.order_price:.3f}"
        )
        return order_id

    def run(self) -> None:
        self.start()
        self.query_account_asset()

        stock_info = self.fetch_ticks(self.symbols)
        if not stock_info:
            print("未获取到任何行情数据。")
            return

        for stock_code in self.symbols:
            tick = stock_info.get(stock_code)
            if tick is None:
                print(f"{stock_code} 未返回 tick 数据，跳过。")
                continue

            position = self.query_position(stock_code)
            available_volume = safe_int(getattr(position, "can_use_volume", 0))
            total_volume = safe_int(getattr(position, "volume", 0))
            open_price = safe_float(getattr(position, "open_price", 0))
            market_value = safe_float(getattr(position, "market_value", 0))

            print(
                f"持仓信息: stock={stock_code}, total_volume={total_volume}, "
                f"available_volume={available_volume}, open_price={open_price:.3f}, "
                f"market_value={market_value:.2f}"
            )

            plan = self.build_sell_plan(stock_code, tick, available_volume)
            if plan is None:
                continue

            self.place_order(plan)

    def on_disconnected(self) -> None:
        self.connected = False
        print("交易连接已断开")

    def on_order_error(self, order_error) -> None:
        print("委托报错:", order_error)

    def on_stock_order(self, order) -> None:
        print("委托回报:", order)

    def on_stock_trade(self, trade) -> None:
        print("成交回报:", trade)


def ensure_float_list(values: Any) -> List[float]:
    if not isinstance(values, list):
        return []
    return [safe_float(value) for value in values]


def first_or_zero(values: List[float]) -> float:
    return values[0] if values else 0.0


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def main() -> None:
    strategy = MyStrategy()
    try:
        strategy.run()
    except Exception as exc:
        print(f"策略执行失败: {exc}")
    finally:
        strategy.stop()


if __name__ == "__main__":
    main()
