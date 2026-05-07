import sys
sys.path.append(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")
import datetime
import numpy as np
from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant
import time
import pandas as pd

accID = '2038046457'  # 填写你的资金账号

class MyContext:
    def __init__(self):
        self.today_stock_list = []


class MyStrategy(XtQuantTraderCallback):
    def __init__(self):
        self.ctx = MyContext()
        self.trader = XtQuantTrader(r'C:\东莞证券QMT模拟交易端\userdata_mini', 123456)
        self.trader.register_callback(self)
        self.trader.start()
        self.trader.connect()
        self.acc = StockAccount(accID, 'STOCK')

        account_res = self.trader.query_stock_asset(self.acc)
        print('account_res', account_res)

        if account_res is None:
            print('account_res空了')
        else:
            print('连接正常')

        available_funds = account_res.cash
        print('可用余额: ', available_funds)

    def run(self):
        today_stock_list = ['000892.SZ']
        stock_info = xtdata.get_full_tick(today_stock_list)
        print(stock_info)
        for i in range(0, len(today_stock_list)):
            stock = today_stock_list[i]
            if stock not in stock_info:
                continue

            tick = stock_info[stock]
            lastPrice = tick['lastPrice']
            bidPrice = tick.get('bidPrice', [0])[0]
            bidVol = tick.get('bidVol', [0])[0]

            detail = xtdata.get_instrument_detail(stock)
            print('detail', detail)
            UpStopPrice = detail.get('UpStopPrice', 0)
            DownStopPrice = detail.get('DownStopPrice', 0)

            print('stock', stock, 'lastPrice:', lastPrice, 'bidPrice', bidPrice, 'bidVol', bidVol, 'UpStopPrice',
                  UpStopPrice, 'DownStopPrice', DownStopPrice)

            sell_num = 100
            sell_price = tick.get('askPrice', [0])[4]
            order_id = self.trader.order_stock(
                self.acc,
                stock,
                xtconstant.STOCK_SELL,  # 买入 (注：原图注释为买入，但实际常量为卖出)
                sell_num,  # 100股
                xtconstant.FIX_PRICE,  # 限价单
                sell_price,  # 价格
                # strategy_name='测试策略',
                # remark='测试订单'
            )
            print('下单成功', order_id, 'stock', stock, 'sell_num', sell_num, 'sell_price', sell_price)

if __name__ == '__main__':
    strategy = MyStrategy()
    strategy.run()