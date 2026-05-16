---
module: lines
path: backtrader/lineiterator.py
keywords: lines, data-series, indicator, indexing, minperiod
tags:
  - module-indicator
  - module-backtrader
  - arch-backtesting
---

# Lines 数据线模型

## Purpose

`Lines` 是 backtrader 的底层统一抽象。数据源、指标、策略、运算结果都围绕 lines 工作，所以 `self.data.close[0]`、`self.sma[-1]`、`bt.And(...)` 这些写法才成立。

## Key Files

| File | Role |
|---|---|
| `backtrader/lineiterator.py` | Strategy/Indicator/Observer 的 line iterator 基础 |
| `backtrader/lineseries.py` | line series 包装和别名 |
| `backtrader/linebuffer.py` | line 值的缓冲区 |
| `backtrader/indicator.py` | 指标如何注册 lines |

## 核心规则

| 规则 | 解释 |
|---|---|
| `[0]` 是当前值 | 在 `next` 里，`data.close[0]` 就是当前 bar close |
| `[-1]` 是上一根已输出值 | 不是 Python list 的最后一个全局元素，而是当前时点之前的值 |
| 数据有别名 | `self.data.close` 可读，等价于 `self.data.lines.close` |
| 策略自动拿到数据 | `self.data`, `self.data0`, `self.datas[0]` 都可访问第一个数据 |
| 指标也像数据 | SMA、RSI、MACD 的输出可以继续喂给其他指标 |
| 运算会创建 line 对象 | `self.data.close > self.sma` 在 `__init__` 里创建可延迟计算的对象 |

## Internal Flow

```text
Data Feed lines
  close/high/low/open/volume
        |
        v
Indicator lines
  SMA/RSI/MACD/custom
        |
        v
Strategy.next()
  read line[0], line[-1]
        |
        v
Signals / Orders
```

## 最小周期

指标需要足够历史数据才会输出。例如 20 日 SMA 至少要 20 根 bars。多个指标同时存在时，策略的 `next` 会等到所有相关指标 ready。

> [!important]
> 如果你在 `__init__` 里创建了一个没有保存到 `self.xxx` 的指标，它仍然可能自动注册到策略，并影响最小周期和绘图。

## 常见写法

```python
class MyStrategy(bt.Strategy):
    def __init__(self):
        self.sma = bt.ind.SMA(self.data.close, period=20)
        self.buysig = self.data.close > self.sma

    def next(self):
        if self.buysig[0]:
            self.buy()
```

也可以在 `next` 中直接比较：

```python
if self.sma > self.data.close:
    ...
```

此时比较的是当前值。

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | DataSeries | 数据源提供 OHLC lines |
| Uses | Indicator | 指标声明自己的输出 lines |
| Used by | Strategy | `self.data`, `self.sma`, `next` |
| Used by | Analyzer/Observer | 与策略同频接收状态 |

## Related Notes

- [[Strategy 策略生命周期]]
- [[Indicators Signals 指标与信号]]
- [[Data Feeds 数据接入]]
- [[backtrader 快速开始]]

