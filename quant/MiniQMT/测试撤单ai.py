# encoding: utf-8
"""
MiniQMT 测试撤单脚本（优化版）

保留原始 `测试撤单.py` 不变，本文件提供更稳健的撤单测试逻辑：
1. 先配置 sys.path，再导入 xtquant，避免导入失败。
2. 拆分连接、查资产、查委托、筛选可撤订单、执行撤单等步骤。
3. 修正原脚本里查询单笔订单时的接口传参问题。
4. 不强依赖 pandas，直接使用列表和字典处理订单数据，结构更轻。
5. 撤单前校验订单状态、委托编号和最小挂单时长，避免误撤。
6. 使用 finally 关闭连接，避免异常退出后资源未释放。
"""

import datetime as dt
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


QMT_ROOT = Path(r"C:\东莞证券QMT模拟交易端")
QMT_SITE_PACKAGES = QMT_ROOT / "bin.x64" / "Lib" / "site-packages"
QMT_USERDATA_DIR = QMT_ROOT / "userdata_mini"

if str(QMT_SITE_PACKAGES) not in sys.path:
    sys.path.append(str(QMT_SITE_PACKAGES))


from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount


ACCOUNT_ID = "2038046457"
ACCOUNT_TYPE = "STOCK"
SESSION_ID = int(time.time())
MIN_PENDING_SECONDS = 10

# 常见可撤状态，沿用原脚本的 50/55，并兼容字符串形式。
CANCELABLE_STATUSES = {50, 55, "50", "55"}


class MyStrategy(XtQuantTraderCallback):
    def __init__(
        self,
        account_id: str = ACCOUNT_ID,
        min_pending_seconds: int = MIN_PENDING_SECONDS,
    ) -> None:
        super().__init__()
        self.account_id = account_id
        self.account = StockAccount(account_id, ACCOUNT_TYPE)
        self.min_pending_seconds = min_pending_seconds
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

    def query_orders(self, order_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if order_id is not None:
            order = self.query_one_order(order_id)
            return [order] if order else []

        try:
            orders = self.trader.query_stock_orders(self.account) or []
        except Exception as exc:
            raise RuntimeError(f"查询全部委托失败: {exc}") from exc

        normalized_orders = [self.order_to_dict(order) for order in orders]
        print(f"查询到 {len(normalized_orders)} 笔委托")
        return normalized_orders

    def query_one_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        try:
            order = self.trader.query_stock_order(self.account, order_id)
        except Exception as exc:
            raise RuntimeError(f"查询指定委托失败: order_id={order_id}, {exc}") from exc

        if not order:
            print(f"未查询到指定委托: order_id={order_id}")
            return None

        result = self.order_to_dict(order)
        print("指定委托:", result)
        return result

    def order_to_dict(self, order: Any) -> Dict[str, Any]:
        return {
            "委托编号": safe_int(getattr(order, "order_id", 0)),
            "证券代码": getattr(order, "stock_code", ""),
            "委托价格": safe_float(getattr(order, "price", 0)),
            "委托数量": safe_int(getattr(order, "order_volume", 0)),
            "成交数量": safe_int(getattr(order, "traded_volume", 0)),
            "成交均价": safe_float(getattr(order, "traded_price", 0)),
            "状态": getattr(order, "order_status", ""),
            "时间": safe_int(getattr(order, "order_time", 0)),
            "委托方向": getattr(order, "order_type", ""),
        }

    def is_cancelable(self, order_info: Dict[str, Any]) -> bool:
        order_id = order_info.get("委托编号", 0)
        status = order_info.get("状态")
        order_time = order_info.get("时间", 0)

        if not order_id:
            print("跳过无效委托编号订单:", order_info)
            return False

        if status not in CANCELABLE_STATUSES:
            print(f"订单 {order_id} 状态为 {status}，不在可撤范围内。")
            return False

        pending_seconds = self.get_pending_seconds(order_time)
        if pending_seconds < self.min_pending_seconds:
            print(
                f"订单 {order_id} 挂单仅 {pending_seconds:.1f} 秒，"
                f"小于阈值 {self.min_pending_seconds} 秒，先不撤。"
            )
            return False

        return True

    def get_pending_seconds(self, order_time: int) -> float:
        order_datetime = parse_order_time(order_time)
        if order_datetime is None:
            return 0.0
        return max((dt.datetime.now() - order_datetime).total_seconds(), 0.0)

    def cancel_order(self, order_id: int, stock_code: str = "") -> Any:
        try:
            cancel_result = self.trader.cancel_order_stock(self.account, order_id)
        except Exception as exc:
            raise RuntimeError(f"撤单失败: order_id={order_id}, {exc}") from exc

        print(
            f"已提交撤单: order_id={order_id}, stock={stock_code}, "
            f"cancel_result={cancel_result}"
        )
        return cancel_result

    def handle_cancel_orders(self, order_id: Optional[int] = None) -> None:
        self.start()
        self.query_account_asset()

        orders = self.query_orders(order_id=order_id)
        if not orders:
            print("当前没有可处理的委托。")
            return

        print("委托列表:")
        for order_info in orders:
            print(order_info)

        cancel_count = 0
        for order_info in orders:
            if not self.is_cancelable(order_info):
                continue

            self.cancel_order(
                order_id=order_info["委托编号"],
                stock_code=order_info.get("证券代码", ""),
            )
            cancel_count += 1

        print(f"本次共提交 {cancel_count} 笔撤单请求")

    def on_disconnected(self) -> None:
        self.connected = False
        print("交易连接已断开")

    def on_cancel_error(self, cancel_error) -> None:
        print("撤单报错:", cancel_error)

    def on_stock_order(self, order) -> None:
        print("委托回报:", order)

    def on_stock_trade(self, trade) -> None:
        print("成交回报:", trade)

    def on_order_error(self, order_error) -> None:
        print("委托报错:", order_error)


def parse_order_time(order_time: int) -> Optional[dt.datetime]:
    if not order_time:
        return None

    try:
        order_time_int = int(order_time)
    except (TypeError, ValueError):
        return None

    # 兼容秒级和毫秒级时间戳。
    if order_time_int > 10**12:
        order_time_int = order_time_int / 1000

    try:
        return dt.datetime.fromtimestamp(order_time_int)
    except (OverflowError, OSError, ValueError):
        return None


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
        strategy.handle_cancel_orders()
    except Exception as exc:
        print(f"策略执行失败: {exc}")
    finally:
        strategy.stop()


if __name__ == "__main__":
    main()
