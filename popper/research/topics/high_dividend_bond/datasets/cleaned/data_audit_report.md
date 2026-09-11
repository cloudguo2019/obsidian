# HD-ANCHOR-001 阶段5数据清理和质量审计报告

> [已观察事实｜A] 审计时间：2026-09-10T12:26:29+08:00；流水线：`HD-STAGE5-CLEAN-1.0.0`。本程序未运行策略、未读取锁定集结果、未修改原始文件。

## 1. 本阶段要回答的研究问题

[方法选择｜C] 判断日线、PIT分红和公司行动能否在不回填未来信息、不伪造停牌成交、不重复计算现金分红的前提下形成可复现的清洁输入。

## 2. 需要理解的理论和公式

[方法选择｜C] PIT有效条件为`available_time <= decision_time <= expiry_time`，且存在后继记录时必须满足`decision_time < superseded_time`。只有公告日期时，`available_time`等于公告日之后首个上交所交易日09:30（Asia/Shanghai）。

[方法选择｜C] OHLC约束为`low <= open/close <= high`；交易日价格必须为正、成交量和成交额非负。市场开市但无个股有效日K的日期保持`SUSPENDED_OR_MISSING`并禁止成交。

## 3. 本阶段实际操作

[已观察事实｜A] 三个源表均复制到新目录后进行显式类型转换和稳定排序；删除0行、行情插值0处、未知分红填0共0处。无Xtquant日K的市场开市日仅补充交易日历稳定来源标识，不补价格。所有操作类别记录在`cleaning_log.csv`。

## 4. 已直接执行的操作

[计算结果｜A] 价格表清理前后均为5,543行，其中`TRADING` 5,118行、`SUSPENDED_OR_MISSING` 425行；日期范围2003-11-18至2026-09-09。

[计算结果｜A] 正式PIT表清理前后均为23行，财年范围2003—2025；会议类型计数为{'ANNUAL_GENERAL_MEETING': 21, 'EXTRAORDINARY_GENERAL_MEETING': 2}，证据等级计数为{'A': 19, 'B': 4}。

[计算结果｜A] 公司行动表清理前后均为30行，其中`VALID` 29行、`QUARANTINED` 1行；隔离行被保留但不能进入年度现金分红入账逻辑。

## 5. 仍需要研究者提供的数据或选择

[待办事项｜B] 为满足独立价格交叉核验，应归档一个不依赖Xtquant的600900未复权日线副源；这不阻止阶段5内部一致性审计，但在现行合同下继续阻止正式L2运行。

[待办事项｜C] 2012年前交易经手费连续历史仍不完整；预注册主研究期从2018年开始，故不影响主期，但影响更早期间的成本精确复算。

## 6. 本阶段产物及保存路径

[已观察事实｜A] 清洁Parquet与CSV镜像、清理日志、机器可读清单和本报告均保存在`research/topics/high_dividend_bond/datasets/cleaned/`。

## 7. 验收标准与结果

| 类型与检查 | 观察值 | 期望值 | 结果 | 严重度 |
|---|---:|---:|---|---|
| [计算结果｜A] `PRICE_REQUIRED_COLUMNS` | 30 | >=30 | PASS | ERROR |
| [计算结果｜A] `PRICE_NO_KEY_DUPLICATES` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_DATE_PARSE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_DATETIME_PARSE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_TIMEZONE` | ['Asia/Shanghai'] | ['Asia/Shanghai'] | PASS | ERROR |
| [计算结果｜A] `PRICE_SOURCE` | ['xtquant'] | ['xtquant'] | PASS | ERROR |
| [计算结果｜A] `PRICE_ADJUST_NONE` | ['none'] | ['none'] | PASS | ERROR |
| [计算结果｜A] `PRICE_RAW_ID_COMPLETE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_RAW_ID_UNIQUE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_TRADE_STATUS_DOMAIN` | ['SUSPENDED_OR_MISSING', 'TRADING'] | ['SUSPENDED_OR_MISSING', 'TRADING'] | PASS | ERROR |
| [计算结果｜A] `PRICE_OHLC_CONSTRAINT` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_POSITIVE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_VOLUME_AMOUNT_NONNEGATIVE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_SUSPENDED_NO_FAKE_OHLC` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_LIMIT_VALIDATION` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PRICE_NO_ROW_DROP` | 5543 | 5543 | PASS | ERROR |
| [计算结果｜A] `PIT_ROW_COUNT` | 23 | 23 | PASS | ERROR |
| [计算结果｜A] `PIT_FISCAL_YEAR_RANGE` | [2003, 2025] | [2003, 2025] | PASS | ERROR |
| [计算结果｜A] `PIT_NO_RECORD_ID_DUPLICATES` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_NO_FISCAL_YEAR_DUPLICATES` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_METHOD_FIXED` | ['SHAREHOLDER_MEETING_CONFIRMED_ANNUAL_DPS_V1'] | ['SHAREHOLDER_MEETING_CONFIRMED_ANNUAL_DPS_V1'] | PASS | ERROR |
| [计算结果｜A] `PIT_EVENT_AFTER_FISCAL_YEAR_END` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_EVENT_NOT_AFTER_ANNOUNCEMENT` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_AVAILABLE_FIRST_OPEN_AFTER_ANNOUNCEMENT` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_EFFECTIVE_EQUALS_AVAILABLE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_EXPIRY_PLUS_365_DAYS` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_SUPERSEDED_EQUALS_NEXT_AVAILABLE` | True | True | PASS | ERROR |
| [计算结果｜A] `PIT_POSITIVE_DPS` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_SOURCE_DOCUMENT_COMPLETE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_SECONDARY_SOURCE_COMPLETE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `PIT_EVIDENCE_LEVEL_DOMAIN` | ['A', 'B'] | ['A', 'B'] | PASS | ERROR |
| [计算结果｜A] `PIT_NO_ROW_DROP` | 23 | 23 | PASS | ERROR |
| [计算结果｜A] `ACTION_NO_ID_DUPLICATES` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `ACTION_REQUIRED_DATES` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `ACTION_DATE_CHRONOLOGY` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `ACTION_STATUS_DOMAIN` | ['QUARANTINED', 'VALID'] | ['QUARANTINED', 'VALID'] | PASS | ERROR |
| [计算结果｜A] `ACTION_VALID_CASH_NONNEGATIVE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `ACTION_SOURCE_DOCUMENT_COMPLETE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `ACTION_RAW_ID_COMPLETE` | 0 | 0 | PASS | ERROR |
| [计算结果｜A] `ACTION_NO_ROW_DROP` | 30 | 30 | PASS | ERROR |
| [计算结果｜A] `PIT_COVERAGE_2018_TO_CUTOFF` | 0.99475691 | >=0.80 | PASS | ERROR |

[计算结果｜A] 结构性错误数为0，警告数为0。阶段5内部结构与时序审计结果为`PASS`。

[计算结果｜A] 2018-01-01至2026-09-09的有效交易日PIT覆盖率为99.4757%（2087/2098），预注册门槛为至少80%；未覆盖交易日11个。

[计算结果｜A] 未覆盖交易日为：2019-05-21, 2019-05-22, 2019-05-23, 2019-05-24, 2021-05-25, 2021-05-26, 2021-05-27, 2021-05-28, 2021-05-31, 2021-06-01, 2024-05-24。这些日期来自相邻年度确认间隔超过365自然日形成的真实失效窗口，未进行无限期前向填充。

## 8. 已发现的问题和证据等级

[已观察事实｜A] FY2012与FY2013的年度DPS分别由临时股东大会确认，故方法名已在v1.3更正为“股东大会确认”，经济口径和365日有效期未改变。

[已观察事实｜B] FY2003的网上披露日和报纸刊登日存在日期差异；两种记录均不早于2004-05-17进入策略，源表保留差异说明。

[已知限制｜B] `trade_status`和涨跌停价是基于Xtquant日K、交易日历和交易所规则的派生字段，不是交易所逐日状态原始档案；`SUSPENDED_OR_MISSING`故意不把供应商缺失强行解释为停牌。

[已知限制｜B] PIT表有4条B级历史记录；正式结论必须保留这一证据不确定性，不能把B级镜像当作交易所原始档案。

## 9. 是否允许进入下一阶段

[方法选择｜C] `允许在研究者确认后进入阶段6样本划分；正式L2/L3仍关闭`。阶段4数据合同与正式PIT输入已闭环；阶段6不得查看最终锁定集结果，正式回测授权仍为`false`。
