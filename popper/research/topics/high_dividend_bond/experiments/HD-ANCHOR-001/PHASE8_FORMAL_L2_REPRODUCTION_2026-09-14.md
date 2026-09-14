# HD-ANCHOR-001 正式L2版本化复现关闭单

> [已观察事实｜A] 执行日期：2026-09-14（Asia/Shanghai）。本次是阶段11之后对原阶段8正式回顾性L2批次的计算复现，不是新参数、新样本或锁定检验。
>
> [已观察事实｜A] 授权范围：使用冻结Python 3.11.9环境，对`[2022-03-10, 2025-09-10)`执行一次P00—P23×4账户的版本化复现；原结果只读保留，`[2025-09-10, 2026-09-10)`历史伪锁定保持`NOT_OPENED_NOT_READ`。

## 一、研究问题与授权

[研究假设] 本次不重新检验策略经济假设，而是检验：在同一解释器、依赖、代码、数据、协议、样本、`q_RM=900`及随机种子下，原正式L2批次能否确定性复现。

[已观察事实｜A] 研究者先要求“修复python3.11环境，然后重新回测”。环境核验确认Python环境实际健康后，研究助手明确询问是否授权上述精确范围；研究者回复“授权”。机器可读记录为[`FORMAL_L2_REPRODUCTION_AUTHORIZATION_2026-09-14.json`](FORMAL_L2_REPRODUCTION_AUTHORIZATION_2026-09-14.json)。

[方法选择] 本授权只允许一次尝试。复现写入全新路径，不覆盖原阶段8批次；不改变策略、分红、成本、成交、样本、基准或Bootstrap；不运行阶段9/10派生分析，不开启伪锁定、仿真或实盘，`dry_run=true`。

## 二、环境、输入与操作

- [已观察事实｜A] 运行环境：CPython 3.11.9、AkShare 1.18.94、pandas 3.0.5、PyArrow 25.0.1，与冻结记录一致。
- [计算结果｜A] 运行前合成测试31/31通过；原正式L2产物验证通过。
- [计算结果｜A] 复现预检通过3项计划绑定、阶段8冻结生产器及其上游输入哈希；范围为852个会话、851个交易日、24项配置和96条账户路径。
- [方法选择] 复现运行器只重定向一次性尝试、结果和输出路径，数值计算仍调用SHA-256为`d078a902a11d00de1960699c007c8bbbac8fbf99de18e38fd9e2dba7350875ef`的原冻结生产器。
- [已观察事实｜A] 新输出目录为[`formal_l2_reproduction_v1.0/`](formal_l2_reproduction_v1.0/)，原目录`formal_l2_v1.0_prelock/`未被修改。

## 三、复现结果

[计算结果｜A] 状态为`PASS_EXACT_VALUE_REPRODUCTION`。96条登记路径中92条完成；P21因没有可审计的可执行券商现金利率继续保留4条`NOT_RUN`。没有失败文件。

[计算结果｜A] 复现主结果与原结果完全相同：P00期末净资产70,119.18元、总收益16.8653%、CAGR 4.5513%、最大回撤-8.1697%；900股风险匹配基准期末67,858.44元、总收益13.0974%、CAGR 3.5773%、最大回撤-6.1656%；`Delta_CAGR=0.0097393303911286`，60会话Bootstrap 95%区间为`[-0.00367601357822724, 0.0244694483130419]`。

[计算结果｜A] 原先的门槛判断逐字段复现：点估计、绝对回撤、正半年窗、交易频率、PIT覆盖与登记稳健性通过；主区间跨0、平均股票权重差8.4846个百分点、相对回撤恶化2.0041个百分点、344会话修复期、9个转换日和6个转换簇仍不通过。

## 四、新旧输出一致性

| 比较对象 | 复现结果 |
| --- | --- |
| [计算结果｜A] `profile_results.json` | 逐值完全相同，文件SHA-256相同 |
| [计算结果｜A] `window_results.json` | 逐值完全相同，文件SHA-256相同 |
| [计算结果｜A] `bootstrap_intervals.json` | 逐值完全相同，文件SHA-256相同 |
| [计算结果｜A] `daily_accounts.parquet` | 表值完全相同，文件SHA-256相同 |
| [计算结果｜A] `daily_close_signal_and_lagged_orders.parquet` | 表值完全相同，文件SHA-256相同 |
| [计算结果｜A] `auction_outcomes_daily_close_lagged.parquet` | 表值完全相同，文件SHA-256相同 |
| [计算结果｜A] `run_ledger.json` | 移除运行时间戳和版本化输出路径后完全相同 |
| [计算结果｜A] 原始结果关键字段 | `primary_result`、`evaluation`、`integrity`、Bootstrap方法、运行时、锁定状态、证据上限与研究决策逐值相同 |

[计算结果｜A] 独立验证34项通过：77,640行逐日账户、P00 852个会话、最大结果日期2025-09-09；全部已完成路径逐日对账在0.01元内，P00首尾净资产为60,000.00元与70,119.18元。

## 五、证据含义与计数

[计算结果｜A] 本次提供A级计算可复现性证据：在冻结环境和输入下，原正式批次可以精确重现。它排除了“原结果来自不可重复运行或环境漂移”的疑虑。

[已知限制｜A] 本次使用同一回顾性样本，不能增加独立市场信息量、缩窄统计不确定性、修复风险不匹配或升级为L3。研究决策仍为`修改`，证据上限仍为`L2_RETROSPECTIVE`。

[已观察事实｜A] 正式回测计数由1增至2，绩效计算计数由1增至2；暴露校准仍为1，版本化复现计数为1，历史伪锁定开启0，未来锁定开启0，仿真和实盘均未授权。

## 六、产物与下一门禁

- [已观察事实｜A] 事前计划：[`formal_l2_reproduction_plan_v1.0_pre_results.json`](formal_l2_reproduction_plan_v1.0_pre_results.json)
- [已观察事实｜A] 授权：[`FORMAL_L2_REPRODUCTION_AUTHORIZATION_2026-09-14.json`](FORMAL_L2_REPRODUCTION_AUTHORIZATION_2026-09-14.json)
- [已观察事实｜A] 比较结果：[`formal_l2_reproduction_result_v1.0.json`](formal_l2_reproduction_result_v1.0.json)
- [已观察事实｜A] 独立验证：[`formal_l2_reproduction_validation_v1.0.json`](formal_l2_reproduction_validation_v1.0.json)
- [已观察事实｜A] 复现运行器：[`../../scripts/run_stage8_formal_l2_reproduction.py`](../../scripts/run_stage8_formal_l2_reproduction.py)
- [已观察事实｜A] 独立验证器：[`../../scripts/validate_stage8_formal_l2_reproduction.py`](../../scripts/validate_stage8_formal_l2_reproduction.py)

[待办事项｜C] 当前唯一下一门禁恢复为阶段12：研究者是否授权基于阶段11正式报告、环境勘误及本次复现证据，签署最终`接受/观察/修改/淘汰`决策。阶段12不得借机重跑、调参、重选`q_RM`或打开历史伪锁定。

