# ETF 轮动与 MACD 研究档案

> 新对话冷启动：先使用 `$cg-etf-rotation` 并完整读取 [CG ETF Rotation 项目记忆](CG-ETF-ROTATION_MEMORY.md)，再按记忆中的“最小读取集”加载当前阶段文件。项目记忆是索引，代码、配置、数据和实验清单才是事实来源。

> 当前状态（2026-09-18）：阶段0、阶段1已闭环；阶段2理论材料“接受并闭环”；**阶段3预注册草稿v1.0完成，待签署，未闭环**。新增门槛尚未采用；实证证据仍L0。三项研究修复、两项用户接受时钟限制继续生效，继承68/68验收，本轮无新策略测试。正式回测/锁定/仿真/实盘执行与授权均0。当前入口：[阶段3审阅稿](experiments/ETF-REGIME-001/PHASE3_PREREGISTRATION_REVIEW_v1.0.md)、[机器协议](experiments/ETF-REGIME-001/preregistration_draft_v1.0.json)、[阶段3进度与门禁](decisions/PHASE3_REVIEW_2026-09-18_v1.0.md)、[阶段3身份清单](decisions/PHASE3_MANIFEST_2026-09-18_v1.0.json)。

- 实验编号前缀：`ETF`
- 研究定位：趋势、横截面选择、买卖信号和组合管理
- 核心问题：区分横截面选择与单标的趋势判断；区分趋势状态、触发和退出；控制 ETF 池、参数和规则引发的数据挖掘；处理历史 ETF 池、上市时间和幸存者偏差；评价踏空、反复止损和组合换手。

## 初始实验编号示例

- `ETF-REGIME-001`：趋势状态研究
- `ETF-EXIT-003`：退出条件研究

MACD 应作为 ETF 轮动研究层中的状态或触发变量，不应丢失 ETF 池、排名、类别限制和组合约束。

研究材料分别归档到本目录的 `hypotheses/`、`baselines/`、`experiments/`、`decisions/`、`datasets/` 和 `dashboards/`。

当前工程和数据资产的初始核验见 [2026-09-15 初始数据盘点](datasets/INITIAL_DATA_INVENTORY_2026-09-15.md)。

阶段2材料包括[理论与证伪v1.0](hypotheses/ETF-ROTATION-THEORY_v1.0.md)、[原始来源记录](hypotheses/ETF-ROTATION-SOURCES_2026-09-17_v1.0.md)与[身份清单](decisions/PHASE2_MANIFEST_2026-09-17_v1.0.json)。MACD状态不等同绝对上涨；状态/新鲜交叉、61/78根暖机共同支持、真实小资金账户与公平敞口匹配均已列为后续实验设计要点，尚无MACD有效性结论。

阶段3草稿登记一个主检验、两个候选、五账户×七场景=35单元/样本批次；建议净OOS ΔCalmar≥0.10、配对95%区间、共同78根支持与ENTRY纯入场对照、实际平均/峰值敞口差≤2/3pp。新增值待签署；15项真实数据/费用/现金收益/样本/基准/运行身份尚未建立。原八日工程资料接触登记为已查看，2026档案保留段不称最终未触碰锁，最终锁拟前瞻12月，具体身份待阶段6。默认只读身份检查：`scripts/validate_phase3_draft_v1.py`；阶段3设计签署不等于正式批次授权。

既有生效规则见[章程v1.2](hypotheses/research_charter_v1.2.md)、[阶段1合并基线](baselines/ETF-BASE-001_PHASE1_BASELINE_v1.0.md)与[阶段1闭环](decisions/PHASE1_CLOSURE_2026-09-17_v1.0.md)。
