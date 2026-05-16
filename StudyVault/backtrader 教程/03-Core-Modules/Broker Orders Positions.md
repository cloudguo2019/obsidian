---
module: broker-orders
path: backtrader/brokers/bbroker.py
keywords: broker, order, position, commission, slippage
tags:
  - module-broker
  - module-backtrader
---

# Broker Orders Positions

## Purpose

Broker 模块负责模拟交易账户：现金、持仓、订单状态、成交价格、佣金、滑点、保证金检查。策略只负责创建订单，是否成交以及以什么价格成交由 broker 决定。

## Key Files

| File | Role |
|---|---|
| `backtrader/brokers/bbroker.py` | 默认模拟 broker: `BackBroker` |
| `backtrader/order.py` | 订单类型、状态、执行记录 |
| `backtrader/position.py` | 持仓对象 |
| `backtrader/comminfo.py` | 佣金和保证金信息 |

## Public Interface

| API | Type | Description |
|---|---|---|
| `cerebro.broker.setcash(amount)` | method | 设置初始现金 |
| `cerebro.broker.getvalue()` | method | 当前账户价值 |
| `cerebro.broker.setcommission(...)` | method | 设置佣金/保证金 |
| `cerebro.broker.set_slippage_perc(...)` | method | 设置百分比滑点 |
| `self.buy()`, `self.sell()` | Strategy method | 创建买/卖订单 |
| `order.status` | property | `Submitted`, `Accepted`, `Completed` 等 |
| `order.executed.price` | property | 成交价格 |
| `trade.pnlcomm` | property | 扣佣后交易盈亏 |

## 订单类型

| 类型 | 含义 |
|---|---|
| `Market` | 默认市价单，通常下一根 bar open 成交 |
| `Close` | 用 session close 逻辑执行 |
| `Limit` | 触及限价才成交 |
| `Stop` | 触及止损价后转市价 |
| `StopLimit` | 触及 stop 后激活 limit |
| `StopTrail`, `StopTrailLimit` | 追踪止损 |

## 订单状态

| 状态 | 应对 |
|---|---|
| `Created` | 刚创建 |
| `Submitted` | 已提交给 broker |
| `Accepted` | broker 接受，尚未成交 |
| `Partial` | 部分成交 |
| `Completed` | 完成成交 |
| `Canceled` / `Expired` | 已取消或过期 |
| `Margin` | 现金/保证金不足 |
| `Rejected` | 被拒绝 |

## Internal Flow

```text
Strategy.next()
  |
  +--> self.buy()/self.sell()
          |
          v
        Order Created
          |
          v
      BackBroker checks cash/margin
          |
          +--> Submitted/Accepted
          +--> Completed/Rejected/Margin
          |
          v
Strategy.notify_order(order)
          |
          v
Trade update -> notify_trade(trade)
```

## 常见陷阱

> [!warning]
> 市价单不是“当前 close 成交”。普通回测中，它通常在下一根 bar 的 open 撮合。

> [!tip]
> 每次发订单后保存到 `self.order`，在订单完成/拒绝前不要重复发同方向订单。否则你可能以为策略只买了一次，实际上每根 bar 都在创建新订单。

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | Order | `BuyOrder`, `SellOrder`, execution bits |
| Uses | Position | 更新持仓 |
| Uses | CommInfoBase | 佣金和保证金 |
| Used by | Strategy | `buy/sell/notify_order/notify_trade` |
| Owned by | Cerebro | 默认 broker 自动创建 |

## Related Notes

- [[Strategy 策略生命周期]]
- [[backtrader 回测执行流]]
- [[Analyzers Sizers Optimization]]
- [[backtrader 快速开始]]

