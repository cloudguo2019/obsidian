import sys
sys.path.append(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")
import xtquant.xtdata as xtdata
from datetime import datetime, timedelta
import time


def get_all_stock_codes():
    """获取沪深京所有A股股票代码"""
    all_stocks = xtdata.get_stock_list_in_sector("沪深京A股")

    return all_stocks


def get_realtime_market_status():
    """
    实时统计涨跌家数（盘中使用）
    返回：(上涨家数，下跌家数，平盘家数，无效数据家数)
    """

    stock_codes = get_all_stock_codes()
    print('stock_codes:', stock_codes)
    quotes = xtdata.get_full_tick(stock_codes)
    print('quotes:', quotes)
    up = down = unchanged = invalid = 0

    for code in stock_codes:
        data = quotes.get(code, {})
        last_price = data.get('lastPrice')
        pre_close = data.get('lastClose')

        # 过滤无效数据
        if last_price is None or pre_close is None or pre_close == 0:
            invalid += 1
            continue

        # 计算涨跌幅（避免浮点误差）
        change_pct = (last_price - pre_close) / pre_close * 100
        if change_pct > 1e-6:
            up += 1
        elif change_pct < -1e-6:
            down += 1
        else:
            unchanged += 1

    return up, down, unchanged, invalid

if __name__ == "__main__":
    print(xtdata.get_stock_list_in_sector("沪深A股"))
    print("=== 实时涨跌统计 ===")
    up, down, unchanged, invalid = get_realtime_market_status()
    print(f"上涨: {up}, 下跌: {down}, 平盘: {unchanged}, 无效数据: {invalid}")