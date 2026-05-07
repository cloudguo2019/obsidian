import sys
sys.path.append(r"C:\东莞证券QMT模拟交易端\bin.x64\Lib\site-packages")
from xtquant import xtdata
import time


def get_all_stocks_with_industry():
    """
    获取所有个股的代码、名称（通过get_instrument_detail）和所属行业
    """

    # 下载最新板块分类信息
    print("正在下载板块数据...")
    xtdata.download_sector_data()

    # 获取所有板块名称
    sectors = xtdata.get_sector_list()
    print(f"共获取到 {len(sectors)} 个板块")

    # 将sectors保存到本地文件
    save_sectors_to_file(sectors, 'qmt_概念板块.txt')

    # 存储所有股票信息
    all_stocks_info = {}

    # 遍历所有板块，收集股票信息
    for i, sector in enumerate(sectors):
        try:
            # 获取该板块下的股票列表
            stocks = xtdata.get_stock_list_in_sector(sector)

            for stock_code in stocks:
                if stock_code not in all_stocks_info:
                    all_stocks_info[stock_code] = {
                        'code': stock_code,
                        'name': '',  # 稍后通过get_instrument_detail获取名称
                        'industries': []  # 可能属于多个行业
                    }
                all_stocks_info[stock_code]['industries'].append(sector)

            print(f"进度: {i + 1}/{len(sectors)} - 板块 '{sector}' 有 {len(stocks)} 只股票")

            # 添加延迟避免请求过于频繁
            time.sleep(0.01)

        except Exception as e:
            print(f"处理板块 '{sector}' 时出错: {e}")
        # break

        # 获取股票名称 (改用get_instrument_detail)
        print("正在获取股票名称...")

    for idx, stock_code in enumerate(list(all_stocks_info.keys())):
        try:
            # 调用get_instrument_detail获取详细信息
            detail = xtdata.get_instrument_detail(stock_code)
            # 提取名称（字段为InstrumentName）
            stock_name = detail.get('InstrumentName', '未知')
            all_stocks_info[stock_code]['name'] = stock_name

            # 打印进度（每100只股票显示一次）
            if (idx + 1) % 100 == 0:
                print(f"已获取 {idx + 1}/{len(all_stocks_info)} 只股票名称")

        except Exception as e:
            print(f"获取股票 {stock_code} 名称失败: {e}")
            all_stocks_info[stock_code]['name'] = '未知'

        # 控制请求频率，避免接口限制
        # time.sleep(0.005)

    return all_stocks_info

def save_sectors_to_file(sectors, filename='qmt_概念板块.txt'):
    """将板块列表保存到txt文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("QMT概念板块列表\n")
        f.write("=" * 50 + "\n")
        f.write(f"共 {len(sectors)} 个板块\n\n")

        # 按字母顺序排序
        sorted_sectors = sorted(sectors)

        for i, sector in enumerate(sorted_sectors, 1):
            f.write(f"{i:3d}. {sector}\n")

    print(f"板块列表已保存到 {filename}")

def save_to_txt(stocks_info, filename='stock_industry_info.txt'):
    """将股票信息保存到txt文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("代码\t名称\t所属行业\n")
        f.write("-" * 100 + "\n")
        # 按股票代码排序
        for stock in sorted(stocks_info.values(), key=lambda x: x['code']):
            industries_str = ', '.join(stock['industries'])
            f.write(f"{stock['code']}\t{stock['name']}\t{industries_str}\n")
    print(f"数据已保存到 {filename}, 共 {len(stocks_info)} 只股票")


def save_by_industry(stocks_info, filename='stock_by_industry.txt'):
    """按行业分类保存股票信息"""
    industry_to_stocks = {}
    for stock_info in stocks_info.values():
        for industry in stock_info['industries']:
            if industry not in industry_to_stocks:
                industry_to_stocks[industry] = []
            industry_to_stocks[industry].append(f"{stock_info['code']}\t{stock_info['name']}")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("按行业分类的股票列表\n")
        f.write("=" * 100 + "\n\n")
        for industry in sorted(industry_to_stocks.keys()):
            f.write(f"{industry}:\n")
            for stock_line in sorted(industry_to_stocks[industry]):
                f.write(f"  {stock_line}\n")
            f.write(f"  共 {len(industry_to_stocks[industry])} 只股票\n\n")
    print(f"按行业分类的数据已保存到 {filename}")

if __name__ == "__main__":
    # 测试get_instrument_detail获取名称
    print("\n开始获取股票行业信息...")
    stocks_info = get_all_stocks_with_industry()

    print(f"\n共获取到 {len(stocks_info)} 只股票的信息")
    save_to_txt(stocks_info, 'all_stocks_industry_info.txt')
    save_by_industry(stocks_info, 'stocks_grouped_by_industry.txt')

    # 统计信息
    print("\n统计信息:")
    print(f"总股票数量: {len(stocks_info)}")
    avg_industries = sum(len(info['industries']) for info in stocks_info.values()) / len(stocks_info)
    print(f"平均每个股票属于 {avg_industries:.2f} 个行业")

    # 示例输出
    print("\n前10只股票信息示例:")
    for stock in sorted(stocks_info.values(), key=lambda x: x['code'])[:10]:
        industries_str = ', '.join(stock['industries'][:3])
        if len(stock['industries']) > 3:
            industries_str += f" ...等{len(stock['industries'])}个行业"
        print(f"{stock['code']}\t{stock['name']}\t{industries_str}")