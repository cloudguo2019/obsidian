# 高股息类债策略研究档案

- 实验编号前缀：`HD`
- 研究定位：估值、现金流、库存管理和网格执行
- 核心问题：将基本面估值转换为目标仓位；区分长期持仓与可交易库存；组合基本面价格锚与市场行为价格锚；正确处理历史分红预期、除权和现金分红；检验网格交易是否创造净增量。

## 初始实验编号示例

- `HD-BASE-000`：核心仓＋现金不动
- `HD-BASE-001`：等资金静态持有
- `HD-ANCHOR-001`：现有股息率档位＋滞回
- `HD-ANCHOR-002`：成交量密集价网格
- `HD-ANCHOR-003`：股息率定库存＋HVN定执行
- `HD-EXEC-001`：下一交易日开盘成交（保守执行基准）
- `HD-EXEC-002`：历史盘中数据模拟收盘竞价

研究材料分别归档到本目录的 `hypotheses/`、`baselines/`、`experiments/`、`decisions/`、`datasets/` 和 `dashboards/`。

## 当前阶段产物

- [已观察事实] 阶段0：[研究章程](hypotheses/research_charter.md)。
- [已观察事实] 阶段1：[HD-ANCHOR-001策略规格](baselines/HD-ANCHOR-001_SPEC.md)。
- [已观察事实] 阶段2：[理论机制、因果链与可证伪预测](hypotheses/HD-ANCHOR-001_THEORY.md)，[原始资料与检索记录](hypotheses/HD-ANCHOR-001_SOURCES.md)。
- [方法选择] 当前主研究执行口径为T日完成收盘后形成信号，T+1收盘集合竞价按T+1官方收盘价成交；禁止同日close信号与同日close成交。历史14:57 Tick口径已由v1.1修订取代。
- [已观察事实] 研究者已确认阶段2理论口径，阶段3产物包括：[方法冻结预注册](experiments/HD-ANCHOR-001/preregistration.yaml)、[方法冻结清单](experiments/HD-ANCHOR-001/method_freeze_manifest_v1.0.json)、[阶段3审阅单](experiments/HD-ANCHOR-001/PHASE3_REVIEW.md)。
- [已观察事实] 2026-09-06已确认阶段3唯一首要指标及通过门槛：样本外年化含分红净增量≥0.5个百分点，95%区间下界>0，且须满足各类护栏；仅风险改善时先观察。
- [已观察事实] 2026-09-06已确认分红预期采用当时最新公告的完整年度税前每股现金分红总额作代理，保留180自然日有效期；过期无有效更新时暂停信号，继续记录持仓与净值。
- [已观察事实] 2026-09-07已确认主实验固定NORMAL作条件检验；REVIEW、STOP_ADD、EXIT只进入L0规则验证，不能将条件检验结果外推为人工基本面闸门有效。
- [已观察事实] 2026-09-07研究者删除P00的0.1%竞价量参与率门槛和单边5bp执行摩擦，并同意其余方法确认包；阶段3升级为`v1.0-methods-frozen`。P00按有效保护限价委托在最终竞价价假设全额成交；5bp/10bp只保留为P06/P07压力测试。
- [方法选择] 阶段3方法门禁已通过，可以进入阶段4数据契约；数据、具体样本日期、实现与完整可执行协议仍待审计后绑定。尚未获得正式L2/L3经济有效性证据，也未授权正式回测、锁定测试、仿真或实盘。
- [计算结果] 标的风险画像：[600900.SH近3个月至10年波动率、最大回撤与修复时间](datasets/600900_UNDERLYING_RISK_WINDOWS_2026-09-04.md)。该文件是税前总回报风险快照，不是策略回测结果。
- [已观察事实] 阶段4：[数据契约v1](datasets/data_contract_v1.md)及[契约哈希清单](datasets/data_contract_v1_manifest.json)。契约定义已完成，但实际价格、PIT分红、公司行动、历史14:57 Tick、费用表及数据清单尚未通过验收，因此当前证据上限仍为L0/L1。
- [已观察事实] 2026-09-08完成[QMTData数据就绪性预审](datasets/data_readiness_audit_2026-09-08.md)：发现一份2003-11-18至2026-07-17的未复权日线、7日收盘阶段样本及六条年度DPS候选；历史14:57输入、最终竞价价、结构化公司行动和历史法定费用表仍不完整。
- [已观察事实] 2026-09-09完成[QMTData数据就绪性二次盘点](datasets/data_readiness_audit_2026-09-09.md)：未复权日线已更新至2026-09-09，8日代理价可与日线收盘核对；六条年度DPS按180日有效期的QMT观测交易日覆盖率为54.07%，历史14:57输入、结构化公司行动、权威交易日历、历史法定费用表及独立价格副源仍未完成，L2/L3门禁继续关闭。
- [方法选择] 2026-09-10研究者确认采用[日线收盘信号、下一交易日收盘竞价成交的v1.1协议修订](experiments/HD-ANCHOR-001/PROTOCOL_AMENDMENT_2026-09-10_DAILY_CLOSE_LAGGED.md)，并新增[机器可读预注册覆盖文件](experiments/HD-ANCHOR-001/preregistration_v1.1_daily_close_lagged.yaml)、[v1.1冻结清单](experiments/HD-ANCHOR-001/method_freeze_manifest_v1.1.json)与[数据契约覆盖文件](datasets/data_contract_v1_1_daily_close_lagged.md)。原v1.0冻结文件保持不变；v1.1取消P00对历史14:57 Tick的依赖，但未授权回测，且PIT分红、公司行动、费税、交易状态与双源价格门禁继续有效。
- [已观察事实] 2026-09-10发现研究者新增的[600900真实现金分红候选表](datasets/600900_cash_dividend_actions_2004_2026.csv)：30条记录的关键日期和现金分红金额字段齐全，含主、副来源；该表尚待阶段5来源、权益、税务和账户对账验收，不能提前视为L2通过。
- [已观察事实] 2026-09-10完成[阶段4数据就绪性第三次盘点](datasets/data_readiness_audit_2026-09-10.md)：23个年度DPS与普通公众股东现金分红逐年一致，但分红预期`available_time`仍为空；按180自然日有效期，2004年以来和2018年以来的交易日覆盖率分别约49.94%和50.72%。因此“年度一次更新＋180日TTL＋覆盖率至少80%”构成结构性协议冲突。阶段5数据工程可开始，L2/L3门禁继续关闭。
- [方法选择] 2026-09-10研究者将分红代理改为“股东大会确认、全年有效、通常一年更新一次”。[v1.2协议修订](experiments/HD-ANCHOR-001/PROTOCOL_AMENDMENT_2026-09-10_FULL_YEAR_DIVIDEND_VALIDITY.md)先冻结365日有效期；逐年核验发现FY2012/FY2013由临时股东大会确认后，另以[v1.3非绩效型事实修订](experiments/HD-ANCHOR-001/PROTOCOL_AMENDMENT_2026-09-10_SHAREHOLDER_MEETING_CONFIRMATION.md)、[机器可读协议](experiments/HD-ANCHOR-001/preregistration_v1.3_shareholder_meeting_confirmed.yaml)和[冻结清单](experiments/HD-ANCHOR-001/method_freeze_manifest_v1.3.json)把方法名更正为`SHAREHOLDER_MEETING_CONFIRMED_ANNUAL_DPS_V1`，其余方法不变。
- [已观察事实] 阶段4已登记[版本化上交所交易日历](../trade_calendar/sse_trade_calendar_19901219_20260909.csv)和[A股交易税费历史版本表](../A股交易税费历史版本表_截至2026-09-09.md)，并生成[600900日线增强表](datasets/derived/600900_daily_enriched_v1.csv)、[交易成本表](datasets/schedules/a_share_transaction_cost_schedule_v1.csv)、[股息税表](datasets/schedules/prc_listed_dividend_tax_schedule_v1.csv)、[输入清单](datasets/stage4_input_manifest_v1.json)及[数据契约冻结清单](datasets/data_contract_v1_2_manifest.json)。2018年后的法定交易费率已覆盖，券商佣金与法定费用分别计收；正式L2仍待AGM可得时间和独立价格副源验收。
- [计算结果] 2026-09-10完成[阶段4闭环](datasets/STAGE4_CLOSEOUT_2026-09-10.md)：[正式PIT源表](datasets/600900_point_in_time_dividend_estimates_v1.csv)覆盖FY2003—FY2025共23条；21条由年度股东大会确认、2条由临时股东大会确认；主研究期PIT有效交易日覆盖率99.475691%，超过80%门槛。
- [计算结果] 阶段5[数据质量审计](datasets/cleaned/data_audit_report.md)通过41项检查、结构错误0项；已生成清洁价格、PIT分红和公司行动Parquet、CSV镜像、[清理日志](datasets/cleaned/cleaning_log.csv)及[SHA-256数据清单](datasets/cleaned/data_manifest.json)。未运行策略，正式回测次数和锁定集开启次数均为0。
- [计算结果] 2026-09-10通过[AkShare/Sina独立未复权价格核验](datasets/akshare_price_crosscheck_2026-09-10.md)：两源各5,118行、日期完全一致，4行OHLC相差0.01元，最大相对差异0.077101%，超过1%的重大差异0行；独立价格副源门禁通过。版本、接口、上游来源和文件哈希见[AkShare副源清单](datasets/akshare_price_source_manifest_v1.json)。
- [计算结果] [阶段5补充记录](datasets/STAGE5_SUPPLEMENT_AKSHARE_AND_PRE2012_FEES.md)确认原始税费MD含2012年前费率，已生成[税费机器表v2](datasets/schedules/a_share_transaction_cost_schedule_v2_pre2012.csv)；2003—2012经手费0.110‰按B级连续性证据入表，早期过户费未知起点继续保留C级。当前读取规则与版本关系见[数据契约v1.4](datasets/data_contract_v1_4_akshare_secondary_and_fee_v2.md)、[契约清单](datasets/data_contract_v1_4_manifest.json)和[阶段5补充清单](datasets/cleaned/data_manifest_v1_1_akshare_and_fee_v2.json)。
- [方法选择] 阶段5数据门禁已通过；正式L2仍因阶段6样本划分、阶段7公平基准及明确运行授权尚未完成而关闭。
- [计算结果] 2026-09-10完成[阶段6候选样本定界](experiments/HD-ANCHOR-001/PHASE6_SAMPLE_SPLIT.md)：36个月开发、6个月验证、42个月/7个半年滚动历史OOS和12个月候选伪锁定期均已按日期元数据确定；历史OOS合计54个月、9个半年窗、1,093个交易日，PIT覆盖率99.9085087%。本次未读取策略绩效，正式运行和锁定结果开启均为0。
- [待办事项] 阶段6日期切分通过，但[机器可读切分](experiments/HD-ANCHOR-001/sample_split_v1.0_pending_confirmation.json)及[清单](experiments/HD-ANCHOR-001/sample_split_manifest_v1.0_pending_confirmation.json)仍待研究者声明既往策略结果接触范围；在声明完成前，2025-09-10至2026-09-10只能标记为伪锁定诊断，阶段7正式冻结继续关闭。

