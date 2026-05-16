---
module: architecture
path: StudyVault/backtrader 教程/01-Architecture
keywords: execution-flow, cerebro, strategy, broker
tags:
  - arch-backtesting
  - module-backtrader
---

# backtrader 回测执行流

## 主流程

```text
1. 创建 Cerebro
2. 设置 broker: cash, commission, slippage, sizer
3. 创建 data feed 并 adddata/resampledata/replaydata
4. addstrategy 或 optstrategy
5. addanalyzer/addobserver/addwriter
6. cerebro.run()
7. 每根 bar:
   data feed 推进 -> indicators 更新 -> strategy.next()
   strategy 发订单 -> broker 在下一轮按规则撮合
   order/trade 通知回到 strategy/analyzer
8. 回测结束:
   strategy.stop() -> analyzer.get_analysis() -> plot/print
```

## 一根 bar 内发生什么

| 阶段 | 谁负责 | 你能控制什么 |
|---|---|---|
| 数据推进 | Data Feed / Cerebro | 数据源、时间范围、timeframe、compression |
| 指标准备 | Lines / Indicator | 指标参数、是否引用不同 timeframe |
| 策略判断 | Strategy | `next` 里的买卖条件、风控逻辑 |
| 创建订单 | Strategy API | `buy`, `sell`, `close`, `exectype`, `price`, `valid` |
| 模拟撮合 | Broker | cash、commission、slippage、order type |
| 结果通知 | Strategy/Analyzer | `notify_order`, `notify_trade`, analyzer hooks |

## 最容易误解的点

> [!warning]
> 在普通模式里，`next` 中看到的是当前 bar 的数据；如果此时创建 `Market` 订单，默认会用下一根 bar 的 open 撮合，而不是当前 close。

> [!tip]
> 如果你的 `next` 比数据第一天晚很多才开始，通常不是 bug，而是指标最小周期在生效。比如 20 日均线至少要有 20 个 bars 才能产生有效值。

## 优化执行流

参数优化把 `addstrategy` 换成 `optstrategy`，传入参数序列：

```python
cerebro.optstrategy(MyStrategy, maperiod=range(10, 31))
cerebro.run(maxcpus=1)
```

默认优化结果可能是轻量对象，里面保留参数和 analyzers。需要完整策略对象时再考虑关闭 `optreturn`。

## Related Notes

- [[Cerebro 运行引擎]]
- [[Strategy 策略生命周期]]
- [[Broker Orders Positions]]
- [[Analyzers Sizers Optimization]]

