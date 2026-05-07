# encoding: utf-8

import sys
sys.path.append(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")

from xtquant import xtdata
import os
import time
import gc
import pandas as pd
from datetime import datetime


SAVE_DIR = r"C:\Users\Guo Chen\quant\MiniQMT\everyday_all_stock"
os.makedirs(SAVE_DIR, exist_ok=True)

PERIOD = "1d"
START_TIME = ""
END_TIME = ""

SLEEP_SECONDS = 0.03
GC_EVERY_N = 50          # 每处理50只股票清理一次内存
SKIP_EXISTS = True       # 已存在CSV则跳过，避免重复处理

ERROR_LOG = os.path.join(SAVE_DIR, "error_log.txt")
SUMMARY_FILE = os.path.join(SAVE_DIR, "summary.txt")


def timestamp_to_date(value):
    if pd.isna(value):
        return ""

    value_str = str(value)

    if value_str.isdigit() and len(value_str) >= 13:
        return datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d")

    if value_str.isdigit() and len(value_str) == 8:
        return datetime.strptime(value_str, "%Y%m%d").strftime("%Y-%m-%d")

    return value_str


def get_all_stock_codes():
    stocks = xtdata.get_stock_list_in_sector("沪深京A股")
    return stocks if stocks else []


def normalize_dataframe(data):
    data = data.copy()

    if data.index.name is not None:
        data.reset_index(inplace=True)
    else:
        if "time" not in data.columns and "stime" not in data.columns:
            data.reset_index(inplace=True)
            if "index" in data.columns:
                data.rename(columns={"index": "stime"}, inplace=True)

    if "time" in data.columns:
        data["date"] = data["time"].map(timestamp_to_date)
    elif "stime" in data.columns:
        data["date"] = data["stime"].map(timestamp_to_date)
    else:
        raise KeyError(f"没有 time/stime 字段，实际字段: {list(data.columns)}")

    cols = list(data.columns)
    cols.remove("date")
    return data[["date"] + cols]


def write_error(msg):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def download_and_save_daily_data(stock_code):
    filename = os.path.join(SAVE_DIR, f"{stock_code}.csv")

    if SKIP_EXISTS and os.path.exists(filename):
        return "skip"

    result = None
    data = None

    try:
        xtdata.download_history_data(
            stock_code,
            period=PERIOD,
            start_time=START_TIME,
            end_time=END_TIME
        )

        result = xtdata.get_market_data_ex(
            field_list=[],
            stock_list=[stock_code],
            period=PERIOD,
            start_time=START_TIME,
            end_time=END_TIME,
            count=-1,
            dividend_type="none",
            fill_data=True
        )

        if result is None or stock_code not in result:
            write_error(f"[无数据] {stock_code}: result为空或无对应key")
            return "fail"

        data = result[stock_code]

        if data is None or data.empty:
            write_error(f"[无数据] {stock_code}: 空DataFrame")
            return "fail"

        data = normalize_dataframe(data)

        data.to_csv(filename, index=False, encoding="utf-8-sig")

        return "success"

    except Exception as e:
        write_error(f"[失败] {stock_code}: {e}")
        return "fail"

    finally:
        del result
        del data
        time.sleep(SLEEP_SECONDS)


def main():
    all_codes = get_all_stock_codes()

    if not all_codes:
        print("未获取到股票列表，请检查 MiniQMT 是否已登录")
        return

    total = len(all_codes)
    success_count = 0
    fail_count = 0
    skip_count = 0

    print(f"共获取到 {total} 只股票")
    print(f"保存目录: {SAVE_DIR}")

    start_time = time.time()

    for i, code in enumerate(all_codes, 1):
        status = download_and_save_daily_data(code)

        if status == "success":
            success_count += 1
        elif status == "skip":
            skip_count += 1
        else:
            fail_count += 1

        if i % 20 == 0 or i == total:
            elapsed = time.time() - start_time
            print(
                f"进度 {i}/{total} | "
                f"成功 {success_count} | "
                f"跳过 {skip_count} | "
                f"失败 {fail_count} | "
                f"耗时 {elapsed / 60:.2f} 分钟"
            )

        if i % GC_EVERY_N == 0:
            gc.collect()

    summary = (
        f"处理完成\n"
        f"总数: {total}\n"
        f"成功: {success_count}\n"
        f"跳过: {skip_count}\n"
        f"失败: {fail_count}\n"
        f"输出目录: {SAVE_DIR}\n"
        f"错误日志: {ERROR_LOG}\n"
    )

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary)

    print("\n" + summary)


if __name__ == "__main__":
    main()