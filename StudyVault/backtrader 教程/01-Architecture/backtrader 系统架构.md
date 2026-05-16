---
module: architecture
path: StudyVault/backtrader 教程/01-Architecture
keywords: architecture, cerebro, event-loop, backtesting
tags:
  - arch-backtesting
  - module-backtrader
---

# backtrader 系统架构

## 一句话模型

`backtrader` 是一个以 `Cerebro` 为装配中心的事件驱动回测框架。用户提供数据源和策略类，框架按 bar 推进数据线，策略在生命周期钩子里读指标、发订单，Broker 模拟撮合，Analyzer/Observer 收集结果。

```text
User Script / btrun
        |
        v
    Cerebro
        |
        +--> Data Feeds --> Lines clock --> Strategy.next()
        |                                  |
        |                                  +--> Indicators / Signals
        |                                  +--> buy/sell/close orders
        |
        +--> BackBroker --> Order status --> notify_order()
        |               --> Trade PnL ----> notify_trade()
        |
        +--> Analyzers / Observers / Writers
        |
        v
   Results / Plot / Analyzer dicts
```

## 核心边界

| 边界 | 职责 | 关键源码 |
|---|---|---|
| Public import facade | 把 broker、feed、strategy、indicator 等对象挂到 `bt.*` | `backtrader/__init__.py` |
| Runtime orchestration | 装配数据、策略、broker、analyzer，并运行循环 | `backtrader/cerebro.py` |
| User strategy API | 生命周期钩子、数据快捷访问、订单和交易通知 | `backtrader/strategy.py` |
| Lines engine | 所有数据/指标的统一时间序列抽象 | `backtrader/lineiterator.py`, `backtrader/linebuffer.py` |
| Data feed abstraction | 把 CSV、Pandas、live feed 转成标准 OHLC lines | `backtrader/feed.py`, `backtrader/feeds/*` |
| Broker simulation | 现金、持仓、订单撮合、佣金、滑点 | `backtrader/brokers/bbroker.py` |
| Result analysis | 运行中或结束后产生 dict-like 指标 | `backtrader/analyzer.py`, `backtrader/analyzers/*` |

## 设计特征

| 特征 | 对使用者的影响 |
|---|---|
| Lines first | 数据、指标、运算结果都可以像时间序列一样被组合。 |
| Index 0 当前值 | 在 `next` 中永远用 `[0]` 读当前 bar，用 `[-1]` 读上一根输出 bar。 |
| Strategy 不接收 data 参数 | 数据由框架自动注入为 `self.datas`, `self.data`, `self.data0`。 |
| 指标自动注册 | 在策略 `__init__` 里创建的指标会影响最小启动周期，并参与绘图。 |
| Broker 默认存在 | 不手动设置 broker 时也有一个默认模拟 broker，初始现金默认来自框架设置。 |
| 可选向量化 | `runonce=True` 时指标可向量化计算，某些实时/省内存模式会关闭它。 |

## 适合怎么学

1. 先把 `Cerebro` 当成“回测容器”，只记添加数据、策略、运行。
2. 再把 `Strategy` 当成“每根 bar 被调用一次的对象”，重点理解 `next` 和通知方法。
3. 然后学习 `Lines`，因为大部分 backtrader 魔法都来自 lines。
4. 最后研究 Broker、Analyzer、Sizer，这些决定结果是否接近真实交易。

## Related Notes

- [[backtrader 学习地图]]
- [[backtrader 回测执行流]]
- [[Cerebro 运行引擎]]
- [[Strategy 策略生命周期]]

