import sys
sys.path.append(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")
from xtquant import xtdata
import os
import pandas as pd
import time
from datetime import datetime

# 设置数据保存目录
SAVE_DIR = r"C:\Users\Guo Chen\quant\MiniQMT\everyday_all_stock"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)


def timestamp_to_datetime(timestamp):
    """将毫秒时间戳转换为标准时间格式"""
    # 将毫秒时间戳转换为秒
    timestamp_sec = timestamp / 1000
    # 转换为datetime对象
    dt = datetime.fromtimestamp(timestamp_sec)
    # 格式化为字符串
    return dt.strftime('%Y-%m-%d')


def get_all_stock_codes():
    """获取沪深京所有A股股票代码"""
    all_stocks = xtdata.get_stock_list_in_sector("沪深京A股")
    return all_stocks


def download_and_save_min_data(stock_code):
    """下载并保存单只股票的分钟数据"""
    try:
        # 订阅行情数据
        xtdata.subscribe_quote(
            stock_code=stock_code,
            period='1d',
            count=-1,
        )

        # 获取市场数据
        df = xtdata.get_market_data_ex(
            # field_list=['time', 'open', 'high', 'low', 'close', 'volume'],
            count=-1,
            stock_list=[stock_code],
            period='1d',
        )

        # 如果数据不为空
        if df is not None and stock_code in df and not df[stock_code].empty:
            # 转换为DataFrame
            data = df[stock_code]

            # 将时间戳转换为标准时间格式
            data['time'] = data['time'].apply(timestamp_to_datetime)

            # 设置文件名
            filename = os.path.join(SAVE_DIR, f"{stock_code}.csv")

            # 保存为CSV文件
            data.to_csv(filename, index=False, encoding='utf-8-sig')

            print(f"成功保存 {stock_code} 的数据，共 {len(data)} 条记录")
            return True
        else:
            print(f"{stock_code} 无数据")
            return False
    except Exception as e:
        print(f"处理 {stock_code} 时出错: {str(e)}")
        return False
    finally:
        time.sleep(0.05)  # 每次请求后暂停0.5秒


def main():
    # 获取所有股票代码
    all_codes = get_all_stock_codes()
    print(f"共获取到 {len(all_codes)} 只股票")

    # 遍历测试股票代码
    for i, code in enumerate(all_codes, 1):
        print(f"正在处理第 {i}/{len(all_codes)} 只股票: {code}")
        download_and_save_min_data(code)

    print("测试股票数据处理完成")

if __name__ == '__main__':
    main()