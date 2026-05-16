---
module: strategy
path: backtrader/strategy.py
keywords: strategy, lifecycle, next, notify-order, notify-trade
tags:
  - module-strategy
  - module-backtrader
---

# Strategy 策略生命周期

## Purpose

`Strategy` 是用户写交易逻辑的主要扩展点。策略类接收框架注入的数据、broker、sizer、analyzers，并在每根 bar 的生命周期钩子中做判断和下单。

## Key Files

| File | Role |
|---|---|
| `backtrader/strategy.py` | `Strategy` 和 `SignalStrategy` 基类 |
| `samples/sigsmacross/sigsmacross.py` | SMA 交叉信号策略示例 |
| `backtrader/lineiterator.py` | 策略作为 line iterator 的生命周期基础 |

## Public Interface

| API | Type | Description |
|---|---|---|
| `params` / `self.p` | class attribute | 策略参数声明与访问 |
| `__init__` | hook | 创建指标、保存数据线引用 |
| `start` | hook | 回测开始 |
| `prenext` | hook | 指标未 ready 时调用 |
| `nextstart` | hook | 第一次 ready 时调用 |
| `next` | hook | 每根 bar 的核心逻辑 |
| `stop` | hook | 回测结束 |
| `buy`, `sell`, `close` | method | 创建订单 |
| `notify_order` | hook | 接收订单状态变化 |
| `notify_trade` | hook | 接收交易 PnL 变化 |
| `getposition(data=None)` | method | 获取持仓 |

## Internal Flow

```text
Cerebro creates Strategy
  |
  +--> inject env/cerebro/broker/sizer/datas
  |
  +--> __init__: create indicators and state
  |
  +--> start
  |
  +--> prenext until indicators ready
  +--> nextstart once
  +--> next repeatedly
          |
          +--> buy/sell creates Order
          +--> Broker evaluates Order
          +--> notify_order / notify_trade
  |
  +--> stop
```

## 标准策略模板

```python
class MyStrategy(bt.Strategy):
    params = dict(period=20)

    def __init__(self):
        self.order = None
        self.sma = bt.ind.SMA(self.data, period=self.p.period)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            self.bar_executed = len(self)
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            print(trade.pnlcomm)

    def next(self):
        if self.order:
            return
        if not self.position and self.data.close[0] > self.sma[0]:
            self.order = self.buy()
        elif self.position and self.data.close[0] < self.sma[0]:
            self.order = self.sell()
```

## 状态管理建议

| 状态 | 为什么需要 |
|---|---|
| `self.order` | 防止一个订单未完成时重复下单 |
| `self.buyprice`, `self.buycomm` | 记录成交价和佣金 |
| `self.bar_executed` | 用 bar 数控制持仓时间 |
| `self.dataclose` | 少写 `self.data.close`，也减少理解成本 |

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | Data feeds | `self.datas`, `self.data` |
| Uses | Broker | `self.broker`, `buy/sell` |
| Uses | Indicators | `bt.ind.*` |
| Used by | Cerebro | `addstrategy`, `optstrategy` |
| Emits | Orders/Trades | `notify_order`, `notify_trade` |

## Testing

- 用一个短 CSV 或 Pandas DataFrame 验证 `next` 是否按预期触发。
- 先打印 `len(self)`, `self.data.datetime.date(0)`, `self.data.close[0]`。
- 每个订单都在 `notify_order` 中记录状态，避免只看 `buy()` 返回值。

## Related Notes

- [[backtrader 回测执行流]]
- [[Broker Orders Positions]]
- [[Indicators Signals 指标与信号]]
- [[backtrader 快速开始]]

