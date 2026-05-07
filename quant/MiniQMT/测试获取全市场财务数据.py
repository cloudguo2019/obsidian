import sys
sys.path.append(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")
from xtquant import xtdata
import pandas as pd
import os
import time

# 设置pandas显示选项
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

# 设置财务数据保存目录
FINANCIAL_SAVE_DIR = r"qmt_financial_data"
if not os.path.exists(FINANCIAL_SAVE_DIR):
    os.makedirs(FINANCIAL_SAVE_DIR)

def get_all_stock_codes():
    """获取沪深京所有A股股票代码"""
    try:
        all_stocks = xtdata.get_stock_list_in_sector("沪深京A股")
        print(f"共获取到 {len(all_stocks)} 只股票")
        return all_stocks
    except Exception as e:
        print(f"获取股票列表失败: {str(e)}")
        # 备用股票列表
        return [
            "000001.SZ", "000002.SZ", "600036.SH", "601318.SH",
            "600519.SH", "000858.SZ", "300750.SZ", "601888.SH"
        ]

def download_stock_financial_data(stock_code, max_retries=3):
    """下载单只股票的财务数据"""
    for attempt in range(max_retries):
        try:
            print(f"正在下载 {stock_code} 的财务数据... (尝试 {attempt + 1}/{max_retries})")

            # 下载财务数据
            xtdata.download_financial_data2(stock_list=[stock_code])

            # 获取财务数据
            financial_data = xtdata.get_financial_data(stock_list=[stock_code])

            if financial_data and stock_code in financial_data:
                return financial_data[stock_code]
            else:
                print(f"{stock_code} 财务数据为空")
                return None

        except Exception as e:
            print(f"下载 {stock_code} 财务数据失败 (尝试 {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)  # 等待2秒后重试
            else:
                return None

    return None


def save_financial_data(stock_code, tables):
    """保存财务数据到文件"""
    stock_save_dir = os.path.join(FINANCIAL_SAVE_DIR, stock_code)
    if not os.path.exists(stock_save_dir):
        os.makedirs(stock_save_dir)

    saved_files = []

    for table_name, df in tables.items():
        try:
            if df is not None and not df.empty:
                # 保存CSV
                filename = f"{stock_save_dir}/{table_name}.csv"
                df.to_csv(filename, encoding='utf-8-sig', index=False)
                saved_files.append(filename)

                print(f"  ✅ 已保存 {table_name} 表: {filename}")
            else:
                print(f"  ⚠️  {table_name} 表数据为空")
        except Exception as e:
            print(f"  ❌ 保存 {table_name} 表失败: {str(e)}")

    return saved_files


def process_single_stock(stock_code, delay=1):
    """处理单只股票的财务数据"""
    print(f"\n{'=' * 60}")
    print(f"处理股票: {stock_code}")
    print(f"{'=' * 60}")

    # 下载财务数据
    tables = download_stock_financial_data(stock_code)

    if tables:
        # 保存数据
        saved_files = save_financial_data(stock_code, tables)

        # 显示数据概览
        print(f"\n{stock_code} 财务数据概览:")
        for table_name, df in tables.items():
            if df is not None and not df.empty:
                print(f"  {table_name}: {len(df)} 行, {len(df.columns)} 列")
                # 显示最新报告期
                if 'm_timetag' in df.columns:
                    latest_period = df['m_timetag'].iloc[-1] if len(df) > 0 else "无数据"
                    print(f"    最新报告期: {latest_period}")

        print(f"✅ 完成 {stock_code}, 保存了 {len(saved_files)} 个文件")
        return True
    else:
        print(f"❌ {stock_code} 财务数据获取失败")
        return False

def main():
    """主函数：获取全市场财务数据"""
    print("开始获取全市场个股财务数据...")

    # 获取所有股票代码
    all_codes = get_all_stock_codes()

    # 限制处理数量（测试时使用）
    # all_codes = all_codes[:10]  # 只处理前10只股票进行测试

    success_count = 0
    failed_count = 0
    failed_stocks = []

    start_time = time.time()

    # 遍历所有股票代码
    for i, stock_code in enumerate(all_codes, 1):
        print(f"\n进度: {i}/{len(all_codes)} ({i / len(all_codes) * 100:.1f}%)")

        if process_single_stock(stock_code):
            success_count += 1
        else:
            failed_count += 1
            failed_stocks.append(stock_code)

        # 进度显示
        if i % 10 == 0:
            elapsed_time = time.time() - start_time
            estimated_total = (elapsed_time / i) * len(all_codes)
            remaining_time = estimated_total - elapsed_time

            print(f"\n📊 进度汇总: 成功 {success_count}, 失败 {failed_count}")
            print(f"⏱️ 已用时间: {elapsed_time / 60:.1f}分钟, 预计剩余: {remaining_time / 60:.1f}分钟")

        # 请求间隔，避免被限制
        # time.sleep(0.5)

    # 生成汇总报告
    total_time = time.time() - start_time
    print(f"\n{'=' * 60}")
    print("🎉 全市场财务数据获取完成！")
    print(f"{'=' * 60}")
    print(f"📈 总股票数量: {len(all_codes)}")
    print(f"✅ 成功处理: {success_count}")
    print(f"❌ 处理失败: {failed_count}")
    print(f"⏱️ 总耗时: {total_time / 60:.2f} 分钟")
    print(f"📁 数据保存路径: {FINANCIAL_SAVE_DIR}")

    if failed_stocks:
        print(f"\n❌ 失败的股票列表 ({len(failed_stocks)} 只):")
        for i, stock in enumerate(failed_stocks[:20]):  # 只显示前20个
            print(f"  {i + 1}. {stock}")
        if len(failed_stocks) > 20:
            print(f"  ... 还有 {len(failed_stocks) - 20} 只失败股票")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {str(e)}")