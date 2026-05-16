---
module: analyzers-sizers-optimization
path: backtrader/analyzer.py
keywords: analyzer, sizer, optimization, performance, risk
tags:
  - module-analyzer
  - module-backtrader
  - module-strategy
---

# Analyzers Sizers Optimization

## Purpose

Analyzer 用来评估策略表现，Sizer 用来决定每次买卖多少，Optimization 用来批量运行不同参数。它们是从“能交易”走向“能研究策略质量”的关键模块。

## Key Files

| File | Role |
|---|---|
| `backtrader/analyzer.py` | `Analyzer` 基类和生命周期 |
| `backtrader/analyzers/*` | 内置分析器 |
| `backtrader/sizer.py` | `Sizer` 基类 |
| `backtrader/sizers/*` | 内置仓位管理器 |
| `backtrader/cerebro.py` | `optstrategy`, `optreturn`, `maxcpus` |

## Analyzer 生命周期

Analyzer 会拿到 `strategy`、`datas` 等引用，并拥有与策略类似的通知方法：

| 方法 | 用途 |
|---|---|
| `start` | 初始化分析状态 |
| `next` | 每根 bar 更新统计 |
| `notify_order` | 观察订单 |
| `notify_trade` | 观察交易 |
| `notify_cashvalue` | 观察现金和账户价值 |
| `stop` | 结束统计 |
| `get_analysis` | 返回 dict-like 结果 |

## Sizer 工作方式

Sizer 的核心是 `_getsizing(comminfo, cash, data, isbuy)`，返回本次交易数量。

```python
cerebro.addsizer(bt.sizers.FixedSize, stake=10)
```

自定义时通常要读取：

| 信息 | 来源 |
|---|---|
| 当前现金 | `cash` 或 `self.broker.getcash()` |
| 当前持仓 | `self.strategy.getposition(data)` |
| 佣金/保证金 | `comminfo` |
| 买卖方向 | `isbuy` |

## Optimization 示例

```python
cerebro.optstrategy(
    MyStrategy,
    fast=range(5, 21),
    slow=range(20, 61),
)
results = cerebro.run(maxcpus=1)
```

> [!warning]
> 参数优化容易过拟合。应该把优化集、验证集、样本外测试分开，并用 analyzer 记录最大回撤、收益波动、交易次数，而不是只看最终资金。

## Internal Flow

```text
Strategy creates trades
  |
  +--> Sizer decides size before order
  |
  +--> Broker updates cash/position
  |
  +--> Analyzer receives notifications
  |
  v
get_analysis() returns metrics
```

## 常见研究配置

| 目标 | 组件 |
|---|---|
| 固定手数 | `bt.sizers.FixedSize` |
| 收益率序列 | `bt.analyzers.TimeReturn` |
| 夏普比率 | `bt.analyzers.SharpeRatio` |
| 交易明细 | `bt.analyzers.TradeAnalyzer` |
| PyFolio 输出 | `bt.analyzers.PyFolio`，注意 README 标记 pyfolio 集成为 deprecated |

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | Strategy | Analyzer 自动持有策略引用 |
| Uses | Broker | 现金、价值、成交 |
| Used by | Cerebro | `addanalyzer`, `addsizer`, `optstrategy` |
| Used by | Research workflow | 结果评估和参数选择 |

## Related Notes

- [[Cerebro 运行引擎]]
- [[Strategy 策略生命周期]]
- [[Broker Orders Positions]]
- [[backtrader 综合练习]]

