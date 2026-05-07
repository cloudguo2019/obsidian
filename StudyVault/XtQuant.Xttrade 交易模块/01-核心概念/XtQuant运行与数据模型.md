---
title: "XtQuant运行与数据模型"
created: 2026-05-07
source_pdf: "xttrader_raw.md"
part: "core-concepts"
keywords:
  - lifecycle
  - xtconstant
  - data-structure
  - account-type
  - order-status
tags:
  - quant-trading
  - xtquant
  - xttrader
  - concept-note
---

# XtQuant运行与数据模型

## 总览表

| 主题 | 关键点 |
| --- | --- |
| 运行逻辑 | Python 策略通过 XtQuant API 与 MiniQMT 交互，完成下单、撤单、查询与主推接收 |
| 生命周期 | `create -> register_callback -> start -> connect -> subscribe -> run_forever -> stop` |
| 数据字典 | `market` `account_type` `order_type` `price_type` `order_status` 是下单/回调解释基础 |
| 核心结构 | `XtAsset` `XtOrder` `XtTrade` `XtPosition` 是最常见读写对象 |

## 1) 运行生命周期

```text
策略启动
  -> 创建 XtQuantTrader(path, session_id)
  -> 注册回调 register_callback(callback)
  -> 启动线程 start()
  -> 建立连接 connect()
  -> 订阅账号 subscribe(account)
  -> 交易/查询/接收推送
  -> stop() 结束
```

> [!important]
> `session_id` 不是随便填。不同 Python 策略应使用不同会话编号，避免通信混淆。

## 2) 数据字典要点

### 市场与账户

- `market`：覆盖沪深北股票、沪深港通、期货、期权等市场枚举。
- `account_type`：常用 `SECURITY_ACCOUNT` `CREDIT_ACCOUNT` `FUTURE_ACCOUNT`。

### 委托与价格

- `order_type`：股票、信用、期货多种风格（六键/四键/两键）以及 ETF 申赎。
- `price_type`：`LATEST_PRICE` 与 `FIX_PRICE` 最常见。

> [!warning]
> 市价类型仅在实盘环境生效，模拟环境通常不支持市价报单。

### 状态语义

- `order_status`：从未报、已报、部成、已成、已撤、废单等完整状态机。
- `account_status`：连接中、登录中、正常、失败、收盘后等账户状态。

## 3) 常用数据结构速记

| 结构体 | 关键字段 | 用途 |
| --- | --- | --- |
| `XtAsset` | `cash` `market_value` `total_asset` | 账户资产快照 |
| `XtOrder` | `stock_code` `order_id` `order_status` | 委托状态追踪 |
| `XtTrade` | `stock_code` `traded_volume` `traded_price` | 成交明细 |
| `XtPosition` | `stock_code` `volume` | 当前持仓 |
| `XtOrderResponse` | `order_id` `seq` | 异步下单回报关联 |
| `XtOrderError` / `XtCancelError` | `error_id` `error_msg` | 失败原因定位 |

## 4) 学习建议

1. 先把枚举和值域对齐到自己的策略常量层。
2. 回调里优先消费 `XtOrder`/`XtTrade`，不要只看查询结果。
3. 对每个策略动作保留 `order_id` 与 `seq`，便于闭环追踪。

## Related Notes

- [[交易接口与回调实战]]
- [[Xttrade 练习题]]

