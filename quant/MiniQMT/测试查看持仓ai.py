# encoding: utf-8
"""
MiniQMT 查看账户资产和持仓（优化版）
"""

import os
import sys
import time

import pandas as pd


QMT_ROOT = r"C:\东莞证券QMT模拟交易端"
QMT_SITE_PACKAGES = os.path.join(QMT_ROOT, "bin.x64", "Lib", "site-packages")
QMT_USERDATA = os.path.join(QMT_ROOT, "userdata_mini")

if QMT_SITE_PACKAGES not in sys.path:
    sys.path.append(QMT_SITE_PACKAGES)

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount


ACCOUNT_ID = "2038046457"
ACCOUNT_TYPE = "STOCK"
SESSION_ID = int(time.time())


class MyStrategy(XtQuantTraderCallback):
    """
    MiniQMT 交易连接和持仓查询示例。
    """

    def __init__(self, account_id=ACCOUNT_ID):
        self.account_id = account_id
        self.account = StockAccount(self.account_id, ACCOUNT_TYPE)
        self.trader = XtQuantTrader(QMT_USERDATA, SESSION_ID)
        self.connected = False

    def start(self):
        """
        启动交易连接，并打印账户资产和持仓。
        """
        self.trader.register_callback(self)
        self.trader.start()

        connect_result = self.trader.connect()
        self.connected = connect_result == 0
        print("connect_result", connect_result)

        if not self.connected:
            print("连接失败，请确认 QMT 已登录、路径正确、账号可用")
            return

        print("连接正常")
        self.print_account_asset()
        self.print_all_positions()
        self.print_one_position("600875.SH")

    def print_account_asset(self):
        """
        查询并打印账户资产。
        """
        account_asset = self.query_account_asset()
        print("account_asset", account_asset)

        if account_asset is None:
            print("账户资产为空")
            return

        print(
            "可用余额:", format_number(account_asset.cash),
            "总资产:", format_number(account_asset.total_asset),
            "股票市值:", format_number(account_asset.market_value)
        )

    def print_all_positions(self):
        """
        查询并打印全部持仓。
        """
        positions = self.get_position()
        if positions.empty:
            print("当前无持仓")
            return

        print("positions")
        print(positions)

        for _, position in positions.iterrows():
            print(position.to_dict())

    def print_one_position(self, stock_code):
        """
        查询并打印指定股票持仓。
        """
        position = self.get_position(stock_code)
        if position is None:
            print("未查询到指定股票持仓", stock_code)
            return

        print("指定股票持仓", stock_code, position)

    def query_account_asset(self):
        """
        查询账户资产。
        """
        try:
            return self.trader.query_stock_asset(self.account)
        except Exception as err:
            print("查询账户资产失败", err)
            return None

    def get_position(self, stock_code=None):
        """
        查询持仓信息。
        :param stock_code: 股票代码，None 表示查询所有持仓
        :return: 指定股票返回 dict 或 None；全部持仓返回 DataFrame
        """
        if stock_code:
            return self.get_one_position(stock_code)
        return self.get_all_positions()

    def get_one_position(self, stock_code):
        """
        查询指定股票持仓。
        """
        try:
            position = self.trader.query_stock_position(self.account, stock_code)
        except Exception as err:
            print("查询指定持仓失败", stock_code, err)
            return None

        if not position:
            return None
        return position_to_dict(position)

    def get_all_positions(self):
        """
        查询全部持仓。
        """
        try:
            positions = self.trader.query_stock_positions(self.account)
        except Exception as err:
            print("查询全部持仓失败", err)
            return empty_positions_dataframe()

        if not positions:
            return empty_positions_dataframe()

        return pd.DataFrame([position_to_dict(position) for position in positions])

    def on_disconnected(self):
        """
        MiniQMT 断线回调。
        """
        self.connected = False
        print("交易连接已断开")


def position_to_dict(position):
    """
    将 xtquant 持仓对象转成字典，便于打印或转 DataFrame。
    """
    return {
        "证券代码": getattr(position, "stock_code", ""),
        "成本价": get_number(position, "open_price"),
        "持仓量": int(get_number(position, "volume")),
        "可用量": int(get_number(position, "can_use_volume")),
        "冻结量": int(get_number(position, "frozen_volume")),
        "市值": get_number(position, "market_value"),
    }


def empty_positions_dataframe():
    """
    返回带固定列名的空持仓 DataFrame。
    """
    return pd.DataFrame(columns=["证券代码", "成本价", "持仓量", "可用量", "冻结量", "市值"])


def get_number(obj, attr_name, default=0.0):
    """
    安全读取对象数字属性。
    """
    try:
        value = getattr(obj, attr_name, default)
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def format_number(value):
    """
    金额格式化。
    """
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "0.00"


if __name__ == "__main__":
    strategy = MyStrategy()
    strategy.start()
