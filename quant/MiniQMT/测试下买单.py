# encoding: utf-8
"""
MiniQMT 测试买单脚本（优化版）

优化点：
1. 先配置 sys.path，再导入 xtquant，避免导入失败。
2. 拆分连接、查询资金、获取行情、下单等步骤，结构更清晰。
3. 对连接失败、资产为空、行情缺失、价格无效、资金不足做了保护。
4. 买入价格选择更稳健，避免直接访问 bidPrice[4] 导致越界。
5. 使用 finally 关闭连接，避免脚本异常退出后资源未释放。
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
TEST_SYMBOLS = ["000001.SZ"]
BUY_VOLUME = 100


@dataclass
class OrderPlan:
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
        buy_volume: int = BUY_VOLUME,
    ) -> None:
        super().__init__()
        self.account_id = account_id
        self.account = StockAccount(account_id, ACCOUNT_TYPE)
        self.symbols = symbols or TEST_SYMBOLS.copy()
        self.buy_volume = buy_volume
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

    def fetch_ticks(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        if not symbols:
            return {}

        stock_info = xtdata.get_full_tick(symbols) or {}
        print(f"成功获取 {len(stock_info)} / {len(symbols)} 只股票的 tick 数据")
        return stock_info

    def build_order_plan(
        self,
        stock_code: str,
        tick: Dict[str, Any],
        available_cash: float,
    ) -> Optional[OrderPlan]:
        if self.buy_volume <= 0 or self.buy_volume % 100 != 0:
            raise ValueError("买入数量必须为正整数，且 A 股需为 100 股的整数倍。")

        detail = xtdata.get_instrument_detail(stock_code) or {}
        last_price = safe_float(tick.get("lastPrice", 0))
        bid_prices = ensure_float_list(tick.get("bidPrice"))
        ask_prices = ensure_float_list(tick.get("askPrice"))
        up_stop_price = safe_float(detail.get("UpStopPrice", 0))
        down_stop_price = safe_float(detail.get("DownStopPrice", 0))

        order_price = self.select_buy_price(bid_prices, ask_prices, last_price, up_stop_price)
        if order_price <= 0:
            print(f"{stock_code} 下单价格无效，跳过。")
            return None

        estimated_amount = order_price * self.buy_volume
        if available_cash < estimated_amount:
            print(
                f"{stock_code} 可用资金不足，"
                f"需要约 {estimated_amount:.2f}，当前仅有 {available_cash:.2f}。"
            )
            return None

        print(
            f"stock={stock_code} last={last_price:.3f} "
            f"buy1={first_or_zero(bid_prices):.3f} "
            f"sell1={first_or_zero(ask_prices):.3f} "
            f"涨停={up_stop_price:.3f} 跌停={down_stop_price:.3f}"
        )
        print(
            f"计划买入: stock={stock_code}, volume={self.buy_volume}, "
            f"price={order_price:.3f}, estimated_amount={estimated_amount:.2f}"
        )

        return OrderPlan(
            stock_code=stock_code,
            order_type=xtconstant.STOCK_BUY,
            order_volume=self.buy_volume,
            price_type=xtconstant.FIX_PRICE,
            order_price=order_price,
        )

    def select_buy_price(
        self,
        bid_prices: List[float],
        ask_prices: List[float],
        last_price: float,
        up_stop_price: float,
    ) -> float:
        for price in ask_prices:
            if price > 0:
                return round(price, 3)

        for price in bid_prices:
            if price > 0:
                return round(price, 3)

        if last_price > 0:
            return round(last_price, 3)

        if up_stop_price > 0:
            return round(up_stop_price, 3)

        return 0.0

    def place_order(self, plan: OrderPlan) -> int:
        order_id = self.trader.order_stock(
            self.account,
            plan.stock_code,
            plan.order_type,
            plan.order_volume,
            plan.price_type,
            plan.order_price,
            strategy_name="测试买单",
        )

        if order_id <= 0:
            raise RuntimeError(f"{plan.stock_code} 下单失败，返回 order_id={order_id}")

        print(
            f"下单成功: order_id={order_id}, stock={plan.stock_code}, "
            f"volume={plan.order_volume}, price={plan.order_price:.3f}"
        )
        return order_id

    def run(self) -> None:
        self.start()
        account_res = self.query_account_asset()
        available_cash = safe_float(getattr(account_res, "cash", 0))

        stock_info = self.fetch_ticks(self.symbols)
        if not stock_info:
            print("未获取到任何行情数据。")
            return

        for stock_code in self.symbols:
            tick = stock_info.get(stock_code)
            if tick is None:
                print(f"{stock_code} 未返回 tick 数据，跳过。")
                continue

            plan = self.build_order_plan(stock_code, tick, available_cash)
            if plan is None:
                continue

            self.place_order(plan)
            available_cash -= plan.order_price * plan.order_volume

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
