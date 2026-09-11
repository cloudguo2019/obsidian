# HD-DATA-CONTRACT-1.2：年度股东大会确认与全年有效期

> [方法选择｜C] 修订日期：2026-09-10（Asia/Shanghai）。本文件只覆盖[`data_contract_v1.md`](data_contract_v1.md)和[`data_contract_v1_1_daily_close_lagged.md`](data_contract_v1_1_daily_close_lagged.md)中的分红预期确认时点与有效期限；其余数据要求继续继承。
>
> [已观察事实｜A] 对应协议为[`preregistration_v1.2_full_year_dividend_validity.yaml`](../experiments/HD-ANCHOR-001/preregistration_v1.2_full_year_dividend_validity.yaml)。

## 1. PIT分红记录

| 字段 | v1.2要求 |
|---|---|
| [方法选择｜C] `estimate_method` | 固定为`AGM_CONFIRMED_ANNUAL_DPS_V1` |
| [方法选择｜C] `event_time` | 年度股东大会审议通过分红方案的事件时间 |
| [方法选择｜C] `announcement_time` | 股东大会决议公告的发布时间；未知时保留空值 |
| [方法选择｜C] `available_time` | 精确发布时间可得时使用该时间；只有日期时取其后首个上交所交易日09:30+08:00 |
| [方法选择｜C] `effective_time` | 与`available_time`一致，不允许提前至财年末、董事会预案日或股东大会召开前 |
| [方法选择｜C] `expected_annual_dividend_per_share` | 股东大会确认的完整年度、普通二级市场持有人税前DPS |
| [方法选择｜C] `expiry_time` | `available_time + 365自然日`；新的合格年度记录可得后旧记录立即停止使用 |
| [方法选择｜C] `source_document` | 股东大会决议公告原文或不可变快照 |

[方法选择｜C] 有效条件为`available_time <= decision_time`且`0 <= estimate_age_days <= 365`。第366个自然日开始过期。

[方法选择｜C] 中期分红、董事会预案、实施公告、登记、除息、到账和重复下载均不能刷新`available_time`；同年度中期与末期只用于核对完整年度总额。

## 2. 已登记的交易日历

[已观察事实｜A] 上交所开市日候选为[`sse_trade_calendar_19901219_20260909.csv`](../../trade_calendar/sse_trade_calendar_19901219_20260909.csv)，覆盖1990-12-19至2026-09-09共8,722个开市日；源快照、构建脚本、验证报告和SHA-256均已归档。

[已观察事实｜B] 主日历来自新浪财经/AKShare解析器，并用上交所2026年休市公告和历史行情边界交叉核对。它不是上交所直接发布的逐日历史主表，正式证据等级为B。

[方法选择｜C] 日期转换、下一交易日和样本窗口可使用该版本化日历；个股停牌仍由600900日线状态表单独判定，不能由市场开市日代替。

## 3. 600900日线增强字段

[已观察事实｜A] 派生表[`derived/600900_daily_enriched_v1.csv`](derived/600900_daily_enriched_v1.csv)保留Xtquant原始OHLCV，并新增`timezone=Asia/Shanghai`、`source=xtquant`、来源版本、日历版本、公司行动版本、行级`raw_record_id`、`trade_status`、`pre_close`、`limit_up`和`limit_down`。

[方法选择｜C] 有有效非零Xtquant日K的开市日标为`TRADING`；市场开市但没有600900日K的日期标为`SUSPENDED_OR_MISSING`并禁止交易，不擅自区分供应商缺失和公司停牌。

[方法选择｜C] 涨跌停价按上交所主板10%规则、0.01元最小价格单位和除权除息参考价派生；公司行动跨停牌期间累积到下一有行情日。派生值标为证据等级B，不冒充Xtquant直接字段。

[计算结果｜A] 2003-11-18至2026-09-09共有5,543个上交所开市日，其中5,118日有Xtquant日K，425日标为`SUSPENDED_OR_MISSING`；26个交易日应用公司行动调整参考价；5,117个可验证有行情日中，OHLC超出派生涨跌停价的记录为0。

## 4. 机器可读税费表

[已观察事实｜A] A股交易税费来源文档为[`A股交易税费历史版本表_截至2026-09-09.md`](../../A股交易税费历史版本表_截至2026-09-09.md)，已转换为[`schedules/a_share_transaction_cost_schedule_v1.csv`](schedules/a_share_transaction_cost_schedule_v1.csv)。

[已观察事实｜A] 个人股息税制度已转换为[`schedules/prc_listed_dividend_tax_schedule_v1.csv`](schedules/prc_listed_dividend_tax_schedule_v1.csv)，按制度版本、持有期和扣税时点拆行。

[已知限制｜A] 交易经手费2012年前的连续历史版本仍不完整；机器表明确标为空值和C级。该缺口不影响2018年开始的预注册主研究期。

[已观察事实｜A] 上交所2023年经手费调整通知明确记载，调整前A股经手费标准为成交金额0.00487%双向收取，2023-08-28起降至0.00341%；因此2015-08-01至2023-08-27已按官方A级费率入表。[上交所通知](https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20230818_10776219.shtml)（检索日期：2026-09-10）。

[方法选择｜C] 券商佣金按成交金额0.01%、每笔父委托最低5元单独计收；印花税、过户费、经手费和证管费按机器表另行计收。该成本模型在正式结果前固定，后续可用真实交割单检查券商“全佣/净佣”语义，但不得据此事后改写P00。

## 5. L2门禁

[方法选择｜C] 当前允许继续阶段5数据清理和账户实现；在AGM决议日期与可得时间、独立价格副源和完整数据清单通过前，不运行正式L2/L3。
