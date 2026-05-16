---
module: exercises
path: StudyVault/backtrader 教程/04-Practice
keywords: practice, onboarding, backtrader, exercises
tags:
  - practice
  - onboarding
  - module-backtrader
---

# backtrader 综合练习

## Related Modules

- [[backtrader 学习地图]]
- [[Cerebro 运行引擎]]
- [[Strategy 策略生命周期]]
- [[Lines 数据线模型]]
- [[Data Feeds 数据接入]]
- [[Broker Orders Positions]]
- [[Indicators Signals 指标与信号]]
- [[Analyzers Sizers Optimization]]

---

## Exercise 1 - Cerebro 装配顺序 [trace]

> 写出从 `bt.Cerebro()` 到 `cerebro.run()` 的最小回测步骤，并说明每一步创建了什么对象。

> [!answer]- 查看答案
> 1. `cerebro = bt.Cerebro()` 创建运行容器和默认 broker。
> 2. `data = bt.feeds...` 创建数据源对象。
> 3. `cerebro.adddata(data)` 把数据交给运行环境。
> 4. `cerebro.addstrategy(MyStrategy)` 注册策略类。
> 5. `cerebro.broker.setcash(...)` 可选，设置初始现金。
> 6. `cerebro.run()` 实例化策略并开始逐 bar 运行。

---

## Exercise 2 - Lines 当前值与历史值 [code reading]

> 在 `next` 中，`self.data.close[0] < self.data.close[-1] < self.data.close[-2]` 表达什么？为什么不能把 `[0]` 理解成数组第一个元素？

> [!answer]- 查看答案
> 它表示当前 close 低于上一根 bar，上一根 bar 又低于再上一根 bar，也就是连续下跌。`[0]` 在 backtrader lines 中是当前时点，不是历史数组开头；`[-1]` 才是上一根已经输出的值。

---

## Exercise 3 - 订单为什么没有当前价成交 [debug]

> 策略在 `next` 中看到 close 为 10.00 并调用 `self.buy()`，日志却显示成交价是下一天 open 的 10.30。你应该如何解释？

> [!answer]- 查看答案
> 普通 `Market` 订单在当前 bar 形成后创建，broker 默认在下一根 bar 的第一个可用价格撮合，通常是 next open。要确认这个过程，应在 `notify_order` 中打印 `order.executed.price` 和 `order.executed.dt`，不要只打印创建订单时的 close。

---

## Exercise 4 - 防止重复下单 [extension]

> 给一个 SMA 策略加入“订单未完成前不再发新单”的逻辑，需要哪些状态变量和钩子？

> [!answer]- 查看答案
> 需要 `self.order = None`。在 `next` 开头写 `if self.order: return`。创建订单时 `self.order = self.buy()` 或 `self.sell()`。在 `notify_order` 中，当订单完成、取消、拒绝或保证金不足后，把 `self.order = None`。

---

## Exercise 5 - PandasData 列映射 [config]

> DataFrame 的列为 `date, open_px, high_px, low_px, close_px, vol`，日期不是 index。如何创建 `PandasData`？

> [!answer]- 查看答案
> ```python
> data = bt.feeds.PandasData(
>     dataname=df,
>     datetime="date",
>     open="open_px",
>     high="high_px",
>     low="low_px",
>     close="close_px",
>     volume="vol",
>     openinterest=None,
> )
> ```

---

## Exercise 6 - 指标最小周期 [debug]

> 你添加了 `SMA(period=20)` 和 `MACD` 后，`next` 不再从第一根 bar 开始。怎么排查？

> [!answer]- 查看答案
> 先打印 `len(self)` 和日期，确认 `next` 何时开始。然后检查所有在 `__init__` 中创建的指标，包括没有赋值给 `self.xxx` 的指标。最慢 ready 的指标会决定 `next` 首次调用时间。需要早期逻辑时可实现 `prenext`。

---

## Exercise 7 - 自定义 Analyzer [extension]

> 想统计每次交易关闭后的净收益列表，应在哪个方法里收集？最终如何返回？

> [!answer]- 查看答案
> 在自定义 `Analyzer` 的 `notify_trade(self, trade)` 中判断 `if trade.isclosed:`，把 `trade.pnlcomm` 加入列表。最后在 `get_analysis` 中返回 dict-like 对象，例如 `{"pnlcomm": self.pnl_list}`。

---

## Exercise 8 - Sizer 设计 [analysis]

> 固定手数和按现金百分比下单有什么不同风险？

> [!answer]- 查看答案
> 固定手数简单稳定，但不同价格资产的风险暴露差异很大。按现金百分比更接近组合资金管理，但必须考虑价格、手续费、保证金和最小交易单位，否则容易出现现金不足或下单数量为 0。

---

## Exercise 9 - 参数优化 [analysis]

> `maperiod=20` 在训练数据里最佳，是否可以直接实盘使用？还需要哪些验证？

> [!answer]- 查看答案
> 不应该直接使用。需要样本外数据验证，最好做 walk-forward 或至少分训练集/验证集/测试集。还要看最大回撤、交易次数、胜率、盈亏比、收益波动，而不是只看最终资金。

---

## Exercise 10 - btrun 安全性 [debug]

> 为什么不建议在不可信输入环境中暴露 `btrun` 参数？

> [!answer]- 查看答案
> `btrun.py` 中部分参数会被 `eval` 成 dict 或对象参数。对于可信本地研究这很方便，但如果接受陌生输入，可能带来代码执行风险。生产或服务化场景应使用白名单解析。

