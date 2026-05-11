---
title: "Xt交易完整实例"
created: 2026-05-08
source_pdf: "code_examples_raw.md"
source_url: "https://dict.thinktrader.net/nativeApi/code_examples.html"
part: "trading"
keywords:
  - xttrader
  - order-flow
  - callbacks
  - reconnect
  - cancel-order
tags:
  - quant-trading
  - xtquant
  - xttrader
  - async-callback
  - risk-control
---

# Xt交易完整实例

## Overview Table

| 主题  | 关键点                                                        |
| --- | ---------------------------------------------------------- |
| 初始化 | `XtQuantTrader(path, session_id)` 创建交易对象，`path` 要匹配券商端/投研端 |
| 回调  | 自定义 `XtQuantTraderCallback`，接收断线、委托、成交、错误、异步响应             |
| 账户  | `StockAccount(account_id, account_type)` 指定资金账号和账号类型       |
| 查询  | 下单前查询资金和持仓，避免超过可用资金或可用数量                                   |
| 下单  | 示例多用 `order_stock_async`，结果通过回调链确认                         |
| 保活  | `run_forever()` 阻塞交易线程，实盘脚本持续接收回调                          |

## 标准交易启动流程

```text
准备 path/session/account
        |
        v
创建 XtQuantTrader
        |
注册 callback
        |
start -> connect -> subscribe(account)
        |
查询资金/持仓
        |
异步下单
        |
回调确认委托/成交/错误
        |
run_forever 保持运行
```

| 步骤     | 示例接口                              | 关键检查                     |
| ------ | --------------------------------- | ------------------------ |
| 创建交易对象 | `XtQuantTrader(path, session_id)` | `session_id` 同时运行的策略不能重复 |
| 注册回调   | `register_callback(callback)`     | 尽量在连接前完成                 |
| 启动线程   | `start()`                         | 后续连接依赖交易线程               |
| 建立连接   | `connect()`                       | 返回 `0` 表示成功              |
| 订阅账户   | `subscribe(acc)`                  | 订阅后才能收到该账号主推             |
| 查询资产   | `query_stock_asset(acc)`          | 用 `m_dCash` 判断可用资金       |
| 查询持仓   | `query_stock_positions(acc)`      | 区分总持仓和可用持仓               |

> [!important]
> 示例里的账号、路径、token 和服务器地址都只是样板。实盘前要替换成本地环境，并先在测试环境走通全流程。

## 异步下单的回调链

网页“下单后通过回调撤单”示例明确给出异步链路：

```text
order_stock_async 发出委托
  -> on_order_stock_async_response 收到异步请求响应
  -> on_stock_order 收到委托状态
  -> cancel_order_stock_sysid_async 发出异步撤单
  -> on_cancel_order_stock_async_response 收到撤单响应
  -> on_stock_order 收到后续委托状态
```

| 回调 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| `on_order_stock_async_response` | 下单请求有响应，拿到 seq/order_id 等 | 不代表成交 |
| `on_stock_order` | 委托状态变化，可读 `order_status`、`order_sysid` | 不一定已经成交 |
| `on_stock_trade` | 成交价格、数量、方向发生变化 | 不代表剩余委托都结束 |
| `on_cancel_order_stock_async_response` | 撤单请求有响应 | 不等于最终撤单完成 |

## 简单买卖示例的风控骨架

| 操作   | 示例做法                                              | 可迁移规则         |
| ---- | ------------------------------------------------- | ------------- |
| 买入   | `buy_amount = min(target_amount, available_cash)` | 目标金额不能超过可用资金  |
| 买入股数 | `int(buy_amount / current_price / 100) * 100`     | 股票数量按 100 股取整 |
| 卖出   | `sell_vol = min(target_vol, available_vol)`       | 卖出不能超过可用持仓    |
| 卖出价格 | 最新价或盘口价                                           | 应结合涨跌停和滑点     |

## 单股、全推和定时实盘

| 模式 | 触发来源 | 适合用途 |
| --- | --- | --- |
| 单股订阅实盘 | 单个标的行情 callback | 单标的观察、快速验证策略逻辑 |
| 全推订阅实盘 | 全推行情 | 多标的扫描、板块策略 |
| 定时判断实盘 | `time.sleep` 定时轮询 | 低频策略、定点判断 |

> [!warning]
> 回调驱动和定时轮询不要混在一起重复下单。示例用 `order_record` 记录 K 线时间和方向，是为了防止同一信号重复触发。

## 交易接口重连

断线示例的关键不是均线策略，而是重连控制：

1. `on_disconnected` 中把全局 `xt_trader` 置空。
2. 主循环里通过 `get_xttrader` 获取可用交易对象。
3. `try_connect` 在有限 `session_id` 范围内随机尝试。
4. 所有 id 都失败后放弃连接，并提示人工处理。

```text
on_disconnected
      |
      v
xt_trader = None
      |
      v
业务循环检测 -> try_connect(有限 session_id)
      |
      +--> 成功：继续策略
      |
      +--> 失败：停止/报警
```

> [!danger]
> 示例特别提醒不要无限循环创建 session，因为每次连接都会创建对接文件，可能占满硬盘并导致系统异常。

## 信用还款和回调撤单

| 示例 | 核心接口 | 学习点 |
| --- | --- | --- |
| 信用账号执行还款 | `order_stock(..., CREDIT_DIRECT_CASH_REPAY, repay_money, FIX_PRICE, -1, ...)` | 特殊业务也走交易接口，但参数语义不同 |
| 下单后回调撤单 | `cancel_order_stock_sysid_async(account, market, order_sysid)` | 使用柜台合同编号撤单，通常要等 `on_stock_order` 给出 `order_sysid` |

## Exam/Test Patterns

| 场景 | 答案 |
| --- | --- |
| 连接成功但收不到账户回调 | 检查是否 `subscribe(account)` 成功 |
| 异步下单有响应但没有成交 | 继续看 `on_stock_order` 和 `on_stock_trade`，不要把响应当成交 |
| 断线后需要自动恢复 | 用有限 session 范围重连，并在耗尽后报警 |
| 下单后想立刻撤单 | 等委托回报拿到有效 `order_sysid`，再异步撤单 |

## Related Notes

- [[课程总览]]
- [[接口速查]]
- [[Xt行情完整实例]]
- [[易错点]]
- [[Xt完整实例练习题]]

