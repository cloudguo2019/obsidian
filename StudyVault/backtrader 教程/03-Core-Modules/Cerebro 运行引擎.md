---
module: cerebro
path: backtrader/cerebro.py
keywords: cerebro, engine, run, optimization, broker
tags:
  - module-cerebro
  - module-backtrader
  - arch-backtesting
---

# Cerebro 运行引擎

## Purpose

`Cerebro` 是 backtrader 的运行环境和装配中心。它接收数据源、策略、broker、observer、analyzer、writer，然后负责把这些对象放进同一个 bar-by-bar 运行循环。

## Key Files

| File | Role |
|---|---|
| `backtrader/cerebro.py` | `Cerebro` 主类、运行参数、策略/数据装配、优化 |
| `backtrader/__init__.py` | 将 `Cerebro` 导出到 `bt.Cerebro` |
| `backtrader/btrun/btrun.py` | 命令行方式装配 Cerebro |

## Public Interface

| API | Type | Description |
|---|---|---|
| `Cerebro(preload=True, runonce=True, ...)` | class | 创建运行环境 |
| `adddata(data)` | method | 添加普通数据源 |
| `resampledata(data, timeframe, compression)` | method | 把数据重采样到更大周期 |
| `replaydata(data, timeframe, compression)` | method | 逐步 replay 到新周期 |
| `addstrategy(cls, **kwargs)` | method | 添加一个策略 |
| `optstrategy(cls, **kwargs)` | method | 对参数序列做优化 |
| `addanalyzer`, `addobserver`, `addsizer` | method | 增加评估、观察、仓位管理组件 |
| `run()` | method | 启动运行循环 |
| `plot()` | method | 绘图 |

## Internal Flow

```text
User code
  |
  v
Cerebro.__init__
  |
  +--> default BackBroker
  +--> data/strategy/analyzer queues
  |
adddata/addstrategy/addanalyzer
  |
  v
run()
  |
  +--> preload data if enabled
  +--> instantiate strategies
  +--> wire broker/sizer/analyzers/observers
  +--> iterate bars
  +--> collect results
```

## 重要参数

| 参数 | 默认 | 影响 |
|---|---|---|
| `preload` | `True` | 预加载数据，离线回测更快 |
| `runonce` | `True` | 指标向量化计算，实时模式会关闭 |
| `live` | `False` | 开启 live 行为，会关闭 `preload` 和 `runonce` |
| `maxcpus` | `None` | 优化时使用多少 CPU |
| `stdstats` | `True` | 自动添加默认 broker/trade/buysell observers |
| `exactbars` | `False` | 控制内存节省，可能影响 plotting 和 preload |
| `optreturn` | `True` | 优化返回轻量对象，只保留参数和 analyzers |
| `cheat_on_open` | `False` | 允许 open 前执行特殊逻辑 |

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | Broker | `BackBroker` |
| Uses | Strategy | `Strategy`, `SignalStrategy` |
| Uses | Data feeds | `adddata`, `resampledata`, `replaydata` |
| Uses | Analyzer/Observer/Writer | `addanalyzer`, `addobserver`, `addwriter` |
| Used by | User script | `bt.Cerebro()` |
| Used by | CLI | `btrun()` |

## Testing

- 源码项目本身是 Python package，可通过样例脚本和 `btrun` 验证。
- 学习时建议用极小 CSV/Pandas 数据先跑通 `adddata -> addstrategy -> run`。
- 优化测试时先加 `maxcpus=1`，方便日志顺序稳定。

## Related Notes

- [[backtrader 系统架构]]
- [[backtrader 回测执行流]]
- [[Strategy 策略生命周期]]
- [[Analyzers Sizers Optimization]]

