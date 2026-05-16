---
module: dashboard
path: StudyVault/backtrader 教程/00-Dashboard
keywords: backtrader, tutorial, onboarding, trading, python
tags:
  - dashboard
  - onboarding
  - arch-backtesting
  - module-backtrader
---

# backtrader 学习地图

> [!info]
> 本教程基于 GitHub 仓库 [mementum/backtrader](https://github.com/mementum/backtrader)、官方 quickstart/concepts 文档，以及核心源码文件整理。目标是让你能从“跑通第一个回测”走到“理解框架内部如何调度策略、数据、订单和分析器”。

## 架构总览

- 架构模式: 单进程事件驱动回测引擎，`Cerebro` 负责装配和运行。
- 技术栈: Python package, console script `btrun`, optional `matplotlib`, optional live broker/data integrations.
- 核心入口: `backtrader/__init__.py`, `backtrader/cerebro.py`, `backtrader/strategy.py`.
- 先读: [[backtrader 系统架构]]
- 再读: [[backtrader 回测执行流]]

## 模块地图

| 模块 | 学习目的 | 关键文件 | 笔记 |
|---|---|---|---|
| Cerebro | 理解如何添加数据、策略、分析器并启动 run | `backtrader/cerebro.py` | [[Cerebro 运行引擎]] |
| Strategy | 掌握策略生命周期、`next`、订单通知、交易通知 | `backtrader/strategy.py` | [[Strategy 策略生命周期]] |
| Lines | 掌握 `data.close[0]`、`[-1]`、指标延迟和最小周期 | `backtrader/lineiterator.py` | [[Lines 数据线模型]] |
| Data Feeds | 学会 CSV、Pandas、Yahoo 等数据接入方式 | `backtrader/feed.py`, `backtrader/feeds/*` | [[Data Feeds 数据接入]] |
| Broker and Orders | 理解撮合、现金、订单状态、佣金、滑点 | `backtrader/brokers/bbroker.py`, `backtrader/order.py` | [[Broker Orders Positions]] |
| Indicators and Signals | 学会指标声明、自动注册、信号策略 | `backtrader/indicator.py`, `samples/sigsmacross/sigsmacross.py` | [[Indicators Signals 指标与信号]] |
| Analyzers Sizers Optimization | 学会评估结果、仓位规模、参数优化 | `backtrader/analyzer.py`, `backtrader/sizer.py` | [[Analyzers Sizers Optimization]] |
| btrun CLI | 理解命令行如何装配同一套 Cerebro 流程 | `backtrader/btrun/btrun.py` | [[btrun 命令行入口]] |

## API Surface

| 类型 | API / 命令 | 用途 | 相关笔记 |
|---|---|---|---|
| Engine | `bt.Cerebro()` | 创建运行环境 | [[Cerebro 运行引擎]] |
| Engine | `cerebro.adddata(data)` | 添加数据源 | [[Data Feeds 数据接入]] |
| Engine | `cerebro.addstrategy(MyStrategy, **params)` | 添加普通策略 | [[Strategy 策略生命周期]] |
| Engine | `cerebro.optstrategy(MyStrategy, param=range(...))` | 参数优化 | [[Analyzers Sizers Optimization]] |
| Engine | `cerebro.run()` | 启动回测/实盘循环 | [[backtrader 回测执行流]] |
| Strategy | `__init__`, `prenext`, `nextstart`, `next`, `stop` | 策略生命周期钩子 | [[Strategy 策略生命周期]] |
| Strategy | `buy()`, `sell()`, `close()` | 创建订单 | [[Broker Orders Positions]] |
| Strategy | `notify_order`, `notify_trade` | 接收订单和交易事件 | [[Strategy 策略生命周期]] |
| Data | `self.data.close[0]`, `self.data.close[-1]` | 当前值和上一根 bar | [[Lines 数据线模型]] |
| CLI | `btrun` / `tools/bt-run.py` | 命令行运行策略、数据、分析器 | [[btrun 命令行入口]] |

## 上手路线

1. [[backtrader 快速开始]] - 跑通最小回测。
2. [[Lines 数据线模型]] - 理解 backtrader 最特别的访问方式。
3. [[Strategy 策略生命周期]] - 写出可交易策略。
4. [[Broker Orders Positions]] - 理解为什么订单不是在当前 close 成交。
5. [[Indicators Signals 指标与信号]] - 把技术指标变成交易逻辑。
6. [[Analyzers Sizers Optimization]] - 做结果评估、仓位控制和参数优化。
7. [[backtrader 综合练习]] - 用练习验证你是否真的能改代码。

## 标签索引

| 标签 | 含义 | 使用规则 |
|---|---|---|
| `#arch-backtesting` | 回测框架架构 | 架构、执行流、数据流笔记 |
| `#module-backtrader` | backtrader 总模块 | 每个 backtrader 教程笔记都可附加 |
| `#module-cerebro` | Cerebro 引擎 | 只用于运行编排相关笔记 |
| `#module-strategy` | 策略开发 | 生命周期、下单、通知 |
| `#module-data-feed` | 数据源 | CSV、Pandas、实时数据、resample/replay |
| `#module-broker` | Broker、订单、持仓 | 撮合、现金、佣金、滑点 |
| `#module-indicator` | 指标与 lines 计算 | 指标、信号、最小周期 |
| `#module-analyzer` | 分析器与评估 | analyzers、optimization |
| `#practice` | 练习题 | 只用于练习文件 |

## 推荐学习节奏

- 第 1 天: 读 [[backtrader 快速开始]]，手写一个 `SmaCross`。
- 第 2 天: 读 [[Lines 数据线模型]] 和 [[Data Feeds 数据接入]]，换成自己的 CSV 或 Pandas DataFrame。
- 第 3 天: 读 [[Broker Orders Positions]]，把市价单改成限价/止损逻辑。
- 第 4 天: 读 [[Analyzers Sizers Optimization]]，加入 Sharpe、TimeReturn 或自定义 analyzer。
- 第 5 天: 完成 [[backtrader 综合练习]]，把策略参数优化结果写成复盘。

## Source Notes

- GitHub: [mementum/backtrader](https://github.com/mementum/backtrader)
- 官方文档: [Quickstart](https://www.backtrader.com/docu/quickstart/quickstart/), [Concepts](https://www.backtrader.com/docu/concepts/)
- 核心示例: `samples/sigsmacross/sigsmacross.py`

