import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

QMT_SITE_PACKAGES = Path(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")
QMT_USERDATA_DIR = Path(r"C:\东莞证券QMT模拟交易端\userdata_mini")
ACCOUNT_ID = "2038046457"
SESSION_ID = 123456
DEFAULT_SYMBOLS = ["000001.SZ", "000002.SZ"]


if str(QMT_SITE_PACKAGES) not in sys.path:
    sys.path.append(str(QMT_SITE_PACKAGES))


from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount


@dataclass
class StrategyContext:
    today_stock_list: List[str] = field(default_factory=list)


class MyStrategy(XtQuantTraderCallback):
    def __init__(
        self,
        account_id: str,
        symbols: Optional[List[str]] = None,
        userdata_dir: Path = QMT_USERDATA_DIR,
        session_id: int = SESSION_ID,
    ) -> None:
        super().__init__()
        self.ctx = StrategyContext(today_stock_list=symbols or DEFAULT_SYMBOLS.copy())
        self.account_id = account_id
        self.userdata_dir = str(userdata_dir)
        self.session_id = session_id
        self.acc = StockAccount(account_id, "STOCK")
        self.trader = XtQuantTrader(self.userdata_dir, self.session_id)
        self.is_connected = False

    def connect(self) -> None:
        self.trader.register_callback(self)
        self.trader.start()

        connect_result = self.trader.connect()
        self.is_connected = connect_result == 0
        print(f"connect_result: {connect_result}")

        if not self.is_connected:
            raise RuntimeError("QMT 连接失败，请确认客户端已启动且路径配置正确。")

        print("QMT 连接成功")

    def query_account(self) -> Any:
        account_res = self.trader.query_stock_asset(self.acc)
        print("account_res:", account_res)

        if account_res is None:
            raise RuntimeError("账户资产查询失败，返回结果为空。")

        available_funds = getattr(account_res, "cash", None)
        print(f"可用余额: {available_funds}")
        return account_res

    def fetch_full_tick(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        if not symbols:
            print("股票列表为空，本次不查询行情。")
            return {}

        stock_info = xtdata.get_full_tick(symbols) or {}
        print(f"成功获取 {len(stock_info)} / {len(symbols)} 只股票的 tick 数据")
        return stock_info

    def print_tick_summary(self, symbol: str, tick: Dict[str, Any]) -> None:
        last_price = tick.get("lastPrice", 0)
        bid_price = tick.get("bidPrice", [])
        bid_vol = tick.get("bidVol", [])
        ask_price = tick.get("askPrice", [])
        ask_vol = tick.get("askVol", [])

        detail = xtdata.get_instrument_detail(symbol) or {}
        up_stop_price = detail.get("UpStopPrice", 0)
        down_stop_price = detail.get("DownStopPrice", 0)

        best_bid_price = bid_price[0] if bid_price else None
        best_bid_vol = bid_vol[0] if bid_vol else None
        best_ask_price = ask_price[0] if ask_price else None
        best_ask_vol = ask_vol[0] if ask_vol else None

        print(f"\n股票: {symbol}")
        print(f"最新价: {last_price}")
        print(f"买一价/量: {best_bid_price} / {best_bid_vol}")
        print(f"卖一价/量: {best_ask_price} / {best_ask_vol}")
        print(f"涨停价: {up_stop_price}")
        print(f"跌停价: {down_stop_price}")

    def run(self) -> None:
        self.connect()
        self.query_account()

        stock_info = self.fetch_full_tick(self.ctx.today_stock_list)
        if not stock_info:
            print("未获取到任何行情数据。")
            return

        missing_symbols = [
            symbol for symbol in self.ctx.today_stock_list if symbol not in stock_info
        ]
        if missing_symbols:
            print(f"以下标的未返回 tick 数据: {missing_symbols}")

        for symbol in self.ctx.today_stock_list:
            tick = stock_info.get(symbol)
            if tick is None:
                continue
            self.print_tick_summary(symbol, tick)

    def stop(self) -> None:
        if self.is_connected:
            self.trader.stop()
            self.is_connected = False
            print("QMT 连接已关闭")


def main() -> None:
    strategy = MyStrategy(account_id=ACCOUNT_ID)
    try:
        strategy.run()
    except Exception as exc:
        print(f"策略执行失败: {exc}")
    finally:
        strategy.stop()


if __name__ == "__main__":
    main()
