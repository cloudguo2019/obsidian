# ETF 轮动与 MACD 研究档案

> 新对话冷启动：先使用 `$cg-etf-rotation` 并完整读取 [CG ETF Rotation 项目记忆](CG-ETF-ROTATION_MEMORY.md)，再按记忆中的“最小读取集”加载当前阶段文件。项目记忆是索引，代码、配置、数据和实验清单才是事实来源。

> 当前状态（2026-09-30）：阶段0—2已闭环；**阶段3预注册v1.0已签署并闭环**，[尾盘时段修订v1.1](experiments/ETF-REGIME-001/PHASE3_SESSION_AMENDMENT_v1.1.json)已同次签署。阶段4[数据契约v1.0](datasets/ETF-PHASE4_DATA_CONTRACT_v1.0.md)**设计接受并闭环**，数据就绪未通过；见[签署闭环记录](decisions/PHASE4_SIGNATURE_AND_CLOSURE_2026-09-30_v1.0.md)及[冻结清单](decisions/PHASE4_FREEZE_MANIFEST_2026-09-30_v1.0.json)。早期草稿及[尾盘规则事实更正](decisions/PHASE4_TRADING_SESSION_CORRECTION_2026-09-27_v1.0.md)保留历史身份。下一门禁是阶段5来源盘点与质量审计；缺失的历史数据、真实成本、非零基础滑点数值/版本仍阻止正式经济批次。证据仍L0，正式回测/锁定/仿真/实盘执行与授权均0。阶段3父协议不覆盖：[冻结机器协议](experiments/ETF-REGIME-001/preregistration_v1.0.json)、[签署闭环](decisions/PHASE3_SIGNATURE_AND_CLOSURE_2026-09-25_v1.0.md)、[冻结身份清单](decisions/PHASE3_FREEZE_MANIFEST_2026-09-25_v1.0.json)。

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

阶段3已签设计登记一个主检验、两个候选、五账户×七场景=35单元/样本批次；净OOS ΔCalmar≥0.10、配对95%区间、共同78根支持与ENTRY纯入场对照、实际平均/峰值敞口差≤2/3pp。15项真实数据/费用/现金收益/样本/基准/运行身份尚未建立。原八日工程资料接触登记为已查看，2026档案保留段不称最终未触碰锁，最终锁拟前瞻12月，具体身份待阶段6。默认只读身份检查：`scripts/validate_phase3_freeze_v1.py`；阶段3设计签署不等于正式批次授权。

既有生效规则见[章程v1.2](hypotheses/research_charter_v1.2.md)、[阶段1合并基线](baselines/ETF-BASE-001_PHASE1_BASELINE_v1.0.md)与[阶段1闭环](decisions/PHASE1_CLOSURE_2026-09-17_v1.0.md)。
