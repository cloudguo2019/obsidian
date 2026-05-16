---
module: indicators-signals
path: backtrader/indicator.py
keywords: indicator, signal, lines, sma, crossover
tags:
  - module-indicator
  - module-strategy
  - module-backtrader
---

# Indicators Signals 指标与信号

## Purpose

Indicators 把价格数据转换为新的 lines，Signals 则把指标关系变成更声明式的交易信号。backtrader 的指标不是简单数组，而是能参与延迟计算、最小周期、绘图和跨指标组合的 line 对象。

## Key Files

| File | Role |
|---|---|
| `backtrader/indicator.py` | `Indicator` 基类和自动注册机制 |
| `backtrader/indicators/*` | 内置指标库 |
| `backtrader/signal.py` | 信号策略相关定义 |
| `samples/sigsmacross/sigsmacross.py` | SMA 交叉信号示例 |

## Public Interface

| API | Type | Description |
|---|---|---|
| `bt.ind.SMA(period=20)` | indicator | 简单移动平均 |
| `bt.ind.CrossOver(a, b)` | indicator | 两条线交叉 |
| `bt.SIGNAL_LONG` | signal type | 多头信号 |
| `self.signal_add(bt.SIGNAL_LONG, crossover)` | method | 在 `SignalStrategy` 中注册信号 |
| `lines = ("name",)` | class attr | 自定义指标输出线 |
| `params = dict(period=...)` | class attr | 指标参数 |

## SignalStrategy 示例

```python
class SmaCross(bt.SignalStrategy):
    params = dict(sma1=10, sma2=20)

    def __init__(self):
        sma1 = bt.ind.SMA(period=self.p.sma1)
        sma2 = bt.ind.SMA(period=self.p.sma2)
        crossover = bt.ind.CrossOver(sma1, sma2)
        self.signal_add(bt.SIGNAL_LONG, crossover)
```

这种写法把“什么时候买”的判断交给信号框架，适合简单信号系统。复杂风控、分批下单、组合管理通常还是用普通 `Strategy.next()` 更直观。

## 自定义指标骨架

```python
class MySpread(bt.Indicator):
    lines = ("spread",)
    params = dict(period=20)

    def __init__(self):
        sma = bt.ind.SMA(self.data.close, period=self.p.period)
        self.lines.spread = self.data.close - sma
```

> [!tip]
> 如果可以用 line 运算在 `__init__` 中表达，就优先用声明式写法；只有需要逐 bar 特殊逻辑时才重写 `next`。

## Internal Flow

```text
Data line
  |
  +--> Indicator A
          |
          +--> Indicator B / CrossOver / bt.And
                  |
                  v
          Strategy.next or SignalStrategy
```

## 最小周期与绘图

| 行为 | 影响 |
|---|---|
| 创建 SMA/RSI/MACD | 会增加策略启动所需 bars |
| 不保存指标变量 | 仍可能自动注册到策略 |
| `plot=False` | 指标参与计算但不绘图 |
| 多个指标叠加 | 最慢 ready 的指标决定 `next` 开始时间 |

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | Lines | 指标输入和输出都是 lines |
| Uses | Strategy | 在策略 `__init__` 中创建 |
| Used by | Cerebro | 通过策略间接运行 |
| Used by | Plotting | 默认可绘图 |

## Related Notes

- [[Lines 数据线模型]]
- [[Strategy 策略生命周期]]
- [[backtrader 快速开始]]
- [[Analyzers Sizers Optimization]]

