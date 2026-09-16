# ETF 轮动与 MACD 研究档案

> 新对话冷启动：先使用 `$cg-etf-rotation` 并完整读取 [CG ETF Rotation 项目记忆](CG-ETF-ROTATION_MEMORY.md)，再按记忆中的“最小读取集”加载当前阶段文件。项目记忆是索引，代码、配置、数据和实验清单才是事实来源。

- 实验编号前缀：`ETF`
- 研究定位：趋势、横截面选择、买卖信号和组合管理
- 核心问题：区分横截面选择与单标的趋势判断；区分趋势状态、触发和退出；控制 ETF 池、参数和规则引发的数据挖掘；处理历史 ETF 池、上市时间和幸存者偏差；评价踏空、反复止损和组合换手。

## 初始实验编号示例

- `ETF-REGIME-001`：趋势状态研究
- `ETF-EXIT-003`：退出条件研究

MACD 应作为 ETF 轮动研究层中的状态或触发变量，不应丢失 ETF 池、排名、类别限制和组合约束。

研究材料分别归档到本目录的 `hypotheses/`、`baselines/`、`experiments/`、`decisions/`、`datasets/` 和 `dashboards/`。

当前工程和数据资产的初始核验见 [2026-09-15 初始数据盘点](datasets/INITIAL_DATA_INVENTORY_2026-09-15.md)。
