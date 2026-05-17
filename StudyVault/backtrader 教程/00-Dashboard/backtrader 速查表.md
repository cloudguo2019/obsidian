---
module: dashboard
path: StudyVault/backtrader 教程/00-Dashboard
keywords: backtrader, quick-reference, commands, setup
tags:
  - dashboard
  - quick-reference
  - module-backtrader
---

# backtrader 速查表

## 安装与环境

| 动作     | 命令                                            |
| ------ | --------------------------------------------- |
| 安装基础包  | `pip install backtrader`                      |
| 安装绘图依赖 | `pip install "backtrader[plotting]"`          |
| 从源码使用  | 将源码中的 `backtrader/` 目录放入项目或用 editable install |
| CLI 入口 | `btrun` 或 `tools/bt-run.py`                   |

> [!warning]
> `backtrader` 项目历史较长，README 中列出的 Python 版本较老。现代项目中建议先用隔离虚拟环境验证依赖，尤其是 `matplotlib`、TA-Lib、IB/Oanda 等可选集成。

## 最小回测骨架

```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    def next(self):
        if not self.position:
            self.buy()

cerebro = bt.Cerebro()
cerebro.broker.setcash(100000.0)
cerebro.addstrategy(MyStrategy)
cerebro.adddata(data)
cerebro.run()
print(cerebro.broker.getvalue())
```

## 常用 Cerebro 调用

| 调用 | 作用 | 见 |
|---|---|---|
| `bt.Cerebro()` | 创建运行环境 | [[Cerebro 运行引擎]] |
| `cerebro.adddata(data)` | 添加原始数据 | [[Data Feeds 数据接入]] |
| `cerebro.resampledata(data, timeframe=..., compression=...)` | 重采样 | [[Data Feeds 数据接入]] |
| `cerebro.replaydata(data, timeframe=..., compression=...)` | 逐步 replay | [[Data Feeds 数据接入]] |
| `cerebro.addstrategy(StrategyCls, **kwargs)` | 添加策略 | [[Strategy 策略生命周期]] |
| `cerebro.optstrategy(StrategyCls, period=range(10, 31))` | 参数优化 | [[Analyzers Sizers Optimization]] |
| `cerebro.addsizer(bt.sizers.FixedSize, stake=10)` | 设置仓位规模 | [[Analyzers Sizers Optimization]] |
| `cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")` | 添加分析器 | [[Analyzers Sizers Optimization]] |
| `cerebro.plot()` | 绘图 | [[backtrader 快速开始]] |

## Strategy 生命周期

| 方法 | 什么时候发生 | 用途 |
|---|---|---|
| `__init__` | 策略实例化时 | 建立指标、引用数据线、准备状态变量 |
| `start` | 回测开始 | 初始化日志、外部资源 |
| `prenext` | 指标尚未达到最小周期 | 多周期/指标未 ready 时的过渡处理 |
| `nextstart` | 第一次全部 ready | 一次性启动逻辑 |
| `next` | 每根 bar | 核心交易逻辑 |
| `notify_order` | 订单状态变化 | 记录成交、拒单、保证金不足 |
| `notify_trade` | 交易状态变化 | 记录 PnL |
| `stop` | 回测结束 | 汇总结果 |

## Lines 访问

| 表达式 | 含义 |
|---|---|
| `self.data.close[0]` | 当前 bar 的 close |
| `self.data.close[-1]` | 上一根已输出 bar 的 close |
| `self.data0`, `self.data1` | 第 1、第 2 个数据源 |
| `self.data` | `self.datas[0]` 的快捷名 |
| `self.sma[0]` | 当前指标值 |
| `self.sma > self.data.close` | 在 `next` 中等价于比较当前值 |
| `self.data.close.get(size=10)` | 取最近 10 个值 |

## 常见排错

| 症状 | 优先检查 | 相关笔记 |
|---|---|---|
| `next` 很晚才开始 | 指标最小周期、MACD/SMA 等需要足够 bars | [[Lines 数据线模型]] |
| 策略发了订单但没成交 | 订单状态、现金、下一根 bar open、限价条件 | [[Broker Orders Positions]] |
| Pandas 数据列识别错误 | `PandasData` 的 `datetime/open/high/low/close/volume` 参数 | [[Data Feeds 数据接入]] |
| 优化结果看不到完整策略对象 | `Cerebro(optreturn=True)` 默认返回轻量对象 | [[Analyzers Sizers Optimization]] |
| 绘图失败 | 是否安装 `matplotlib`，以及是否启用 `exactbars` 内存节省 | [[Cerebro 运行引擎]] |

