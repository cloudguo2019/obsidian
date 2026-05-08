---
title: "Xt行情完整实例"
created: 2026-05-08
source_pdf: "code_examples_raw.md"
source_url: "https://dict.thinktrader.net/nativeApi/code_examples.html"
part: "market-data"
keywords:
  - xtdata
  - xtdatacenter
  - market-data
  - quote-subscription
  - adjustment
tags:
  - quant-trading
  - xtquant
  - xtdata
  - xtdatacenter
  - async-callback
---

# Xt行情完整实例

## Overview Table

| 主题 | 关键点 |
| --- | --- |
| 数据来源 | `xtdata` 本质上通过 MiniQmt 处理行情请求，服务端和可获取数据范围与 MiniQmt 一致 |
| 历史数据 | 先补本地数据，再查询；补数接口不直接返回行情 |
| 实时行情 | 先订阅，再用查询接口拿拼接后的历史 + 实时数据，或通过 callback 消费 |
| 服务器连接 | VIP/指定服务器场景用 `xtdatacenter`、连接池和监听端口 |
| 全推与盘口 | `get_full_tick` 可用于最新价、买卖盘、对手价 |
| 衍生处理 | 复权、期货期权映射、指数映射属于行情数据的二次加工 |

## 行情获取主流程

```text
MiniQmt / 行情服务器
        |
        v
xtdata 下载/订阅接口
        |
        +--> 本地历史数据缓存
        |
        +--> 实时订阅数据
        |
        v
get_market_data_ex / callback
```

1. 准备标的列表和周期，例如 `["000001.SZ"]`、`"1d"`。
2. 调用 `download_history_data` 增量下载历史行情。
3. 如需财务或板块数据，额外调用 `download_financial_data`、`download_sector_data`。
4. 用 `get_market_data_ex` 读取本地历史行情。
5. 盘中需要实时行情时，先 `subscribe_quote`。
6. 订阅后再查，查询接口会自动拼接本地历史和实时行情。

> [!important]
> “下载数据”和“读取数据”是两个动作。下载接口负责补足本地缓存，不负责把 DataFrame 直接返回给策略。

## 轮询和回调的区别

| 模式 | 示例动作 | 适合场景 | 风险 |
| --- | --- | --- | --- |
| 固定间隔轮询 | 循环调用 `get_market_data_ex`，`time.sleep(3)` | 低频策略、简单观察 | 延迟由 sleep 决定 |
| 订阅回调 | `subscribe_quote(..., callback=f)` | 事件驱动、需要及时响应 | 回调函数要轻量，主线程要阻塞 |

> [!warning]
> 本地已有数据不会触发 callback。callback 是新增 tick 变化触发，不是“把历史数据重放一遍”。

## VIP 和指定服务器连接

VIP 连接示例的核心顺序是：

```text
set_token
  -> set_allow_optmize_address
  -> set_kline_mirror_enabled / set_kline_mirror_markets
  -> xtdc.init
  -> xtdc.listen
  -> xtdata.connect
  -> get_quote_server_status
```

| 配置 | 含义 |
| --- | --- |
| `set_token` | 设置行情服务认证信息，应早于初始化 |
| `set_allow_optmize_address` | 限定可优选服务器地址池 |
| `set_data_home_dir` | 指定行情数据目录 |
| `set_init_markets` | 限定初始化市场，如 `SH`、`SZ`、`BJ` |
| `listen(port=(58620, 58650))` | 在端口范围内寻找可用监听端口 |
| `connect(port=listen_port)` | Python 行情层连接到本地行情中心 |

指定服务器连接则更强调状态确认：先注册 `watch_quote_server_status`，再创建 `QuoteServer(info)` 并连接，最后通过 `get_quote_server_status` 查看实际站点。

## 全推、对手价和盘口兜底

`get_full_tick([code])` 返回盘口和最新价。示例中卖出时取买一价作为对手价：

```python
fix_price = tick[i]["bidPrice"][0] if tick[i]["bidPrice"][0] != 0 else tick[i]["lastPrice"]
```

| 字段 | 用法 | 备注 |
| --- | --- | --- |
| `lastPrice` | 最新价 | 盘口异常时可做兜底 |
| `bidPrice[0]` | 买一价 | 卖出时常作为对手价参考 |
| `askPrice[0]` | 卖一价 | 买入时常作为对手价参考 |

> [!tip]
> 实盘下单还要结合涨跌停价、最小交易单位、最小变动价位和账户权限，不能只凭盘口数组写死价格。

## 复权计算方式

网页示例给了两类思路：

| 方法 | 公式直觉 | 适合记忆 |
| --- | --- | --- |
| 前复权比例法 | 历史价格乘以相对复权因子 | 对齐到最新价格口径 |
| 后复权比例法 | 价格乘以累计复权因子 | 保留上市以来增长轨迹 |
| 分红配股逐笔法 | 按 `interest`、`allotPrice`、`allotNum`、`stockBonus`、`stockGift` 调整 | 需要解释除权除息细节 |

复权因子的生成逻辑是按行情日期和分红日期推进，分红日期不晚于行情日期时累计因子。

## 合约映射和高频因子共享

| 示例 | 学习重点 |
| --- | --- |
| 商品期货期权代码获取对应期货合约 | 从衍生品代码回到标的合约，便于统一行情和交易对象 |
| 指数代码返回对应期货合约 | 指数策略落到期货合约交易前需要映射 |
| 高频因子数据共享 | 借板块列表/云服务把候选篮子或因子结果共享给其他用户 |

## Exam/Test Patterns

| 场景 | 答案 |
| --- | --- |
| `get_market_data_ex` 查不到历史数据 | 先确认 MiniQmt 数据是否存在，必要时 `download_history_data` |
| callback 没触发 | 检查是否订阅成功、是否有新增 tick、主线程是否被 `xtdata.run()` 阻塞 |
| 指定服务器连接不稳定 | 注册连接状态回调，并用 `get_quote_server_status` 验证 |
| 盘口买一价为 0 | 用最新价或更完整的风控规则兜底 |

## Related Notes

- [[课程总览]]
- [[接口速查]]
- [[Xt交易完整实例]]
- [[易错点]]
- [[Xt完整实例练习题]]

