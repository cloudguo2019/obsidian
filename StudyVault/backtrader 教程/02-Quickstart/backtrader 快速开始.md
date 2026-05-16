---
module: quickstart
path: StudyVault/backtrader 教程/02-Quickstart
keywords: quickstart, cerebro, strategy, data-feed, sma
tags:
  - module-backtrader
  - module-cerebro
  - module-strategy
---

# backtrader 快速开始

## 目标

本笔记把官方 quickstart 压缩成一条可执行路线：创建 `Cerebro`，加数据，加策略，下单，处理通知，加入指标和优化。

## 1. 最小运行

```python
import backtrader as bt

cerebro = bt.Cerebro()
print("Starting:", cerebro.broker.getvalue())
cerebro.run()
print("Final:", cerebro.broker.getvalue())
```

这里没有数据也没有策略，所以资金不会变化。但你已经验证了两件事：

| 观察 | 含义 |
|---|---|
| `Cerebro` 可运行 | 回测容器创建成功 |
| `cerebro.broker` 存在 | 默认 broker 已自动创建 |

## 2. 加数据

CSV 数据常见写法：

```python
import datetime as dt
import backtrader as bt

data = bt.feeds.YahooFinanceCSVData(
    dataname="orcl-1995-2014.txt",
    fromdate=dt.datetime(2000, 1, 1),
    todate=dt.datetime(2000, 12, 31),
    reverse=False,
)

cerebro = bt.Cerebro()
cerebro.adddata(data)
cerebro.broker.setcash(100000.0)
cerebro.run()
```

> [!tip]
> 真实项目里更常用 `GenericCSVData` 或 `PandasData`，因为你可以控制列映射和日期格式。见 [[Data Feeds 数据接入]]。

## 3. 加策略

```python
class PrintClose(bt.Strategy):
    def __init__(self):
        self.close = self.datas[0].close

    def next(self):
        print(self.datas[0].datetime.date(0), self.close[0])

cerebro.addstrategy(PrintClose)
```

关键点：

| 写法 | 意义 |
|---|---|
| `self.datas[0]` | 第一个数据源 |
| `self.data` | `self.datas[0]` 的快捷方式 |
| `self.data.close[0]` | 当前 bar close |
| `self.data.close[-1]` | 上一根已输出 bar close |

## 4. 下单和防重复订单

```python
class BuyAfterThreeDown(bt.Strategy):
    def __init__(self):
        self.close = self.data.close
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            print("executed", order.executed.price)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print("order failed")

        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position:
            if self.close[0] < self.close[-1] < self.close[-2]:
                self.order = self.buy()
```

> [!warning]
> `self.buy()` 返回的是“创建出来的订单”，不是已成交结果。订单状态要在 `notify_order` 中确认。

## 5. 指标策略

```python
class SmaStrategy(bt.Strategy):
    params = dict(maperiod=15)

    def __init__(self):
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data,
            period=self.p.maperiod,
        )
        self.order = None

    def next(self):
        if self.order:
            return

        if not self.position and self.data.close[0] > self.sma[0]:
            self.order = self.buy()
        elif self.position and self.data.close[0] < self.sma[0]:
            self.order = self.sell()
```

指标会影响 `next` 的启动时间。比如 `maperiod=15` 时，前 14 根 bar 还无法给出完整均线值。

## 6. 加仓位、佣金、绘图

```python
cerebro.broker.setcash(1000.0)
cerebro.addsizer(bt.sizers.FixedSize, stake=10)
cerebro.broker.setcommission(commission=0.001)
cerebro.run()
cerebro.plot()
```

## 7. 参数优化

```python
cerebro.optstrategy(SmaStrategy, maperiod=range(10, 31))
cerebro.run(maxcpus=1)
```

优化用于比较参数表现，但不要把“回测里最优”直接当成“实盘里最优”。

## 练习任务

1. 把 SMA 策略改成双均线交叉。
2. 加入 `notify_trade`，输出 `trade.pnlcomm`。
3. 加入 `FixedSize`，比较 `stake=1` 和 `stake=10`。
4. 改成 `PandasData` 输入。
5. 用 `optstrategy` 优化短均线和长均线周期。

## Related Notes

- [[Cerebro 运行引擎]]
- [[Strategy 策略生命周期]]
- [[Lines 数据线模型]]
- [[Broker Orders Positions]]
- [[backtrader 综合练习]]

