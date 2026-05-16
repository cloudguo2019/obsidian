---
module: btrun
path: backtrader/btrun/btrun.py
keywords: cli, btrun, cerebro, command-line
tags:
  - module-backtrader
  - module-cerebro
  - api-cli
---

# btrun 命令行入口

## Purpose

`btrun` 是 backtrader 的命令行入口。它把命令行参数转换成 `Cerebro` 装配过程：选择 data format，添加策略/指标/观察器/分析器，设置 broker，然后运行。

## Key Files

| File | Role |
|---|---|
| `backtrader/btrun/btrun.py` | CLI 主逻辑 |
| `setup.py` | `entry_points={'console_scripts': ['btrun=backtrader.btrun:btrun']}` |
| `tools/bt-run.py` | 脚本入口 |

## Public Interface

| 参数组 | 作用 |
|---|---|
| data format | 选择 `btcsv`, `yahoocsv`, `yahoo`, `ibdata`, `oandadata` 等 |
| `--fromdate`, `--todate` | 数据时间范围 |
| `--resample`, `--replay` | 周期转换 |
| strategies | 动态加载策略类并传参 |
| indicators | 添加指标 |
| analyzers | 添加分析器 |
| broker args | cash、commission、margin、slippage |
| plot args | 运行后绘图 |

## Internal Flow

```text
btrun(pargs)
  |
  v
parse_args
  |
  +--> Cerebro(**cerebro_kwargs)
  +--> getdatas(args) -> adddata/resample/replay
  +--> getobjects(strategies/indicators/analyzers)
  +--> setbroker(args, cerebro)
  +--> cerebro.run()
  +--> print analyzers / plot
```

## 什么时候用 CLI

| 场景 | 是否适合 |
|---|---|
| 快速验证内置数据格式和策略 | 适合 |
| 研究复杂策略状态 | 更建议写 Python 脚本 |
| CI 中跑固定样例 | 适合 |
| 多资产组合、复杂风控 | 更建议写 Python 脚本 |

## 注意点

> [!warning]
> `btrun.py` 中会把若干字符串参数 `eval` 成 dict。只在可信环境里使用，不要把陌生输入直接传给它。

## Related Notes

- [[Cerebro 运行引擎]]
- [[Data Feeds 数据接入]]
- [[Analyzers Sizers Optimization]]
- [[backtrader 速查表]]

