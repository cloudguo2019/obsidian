# HD-ANCHOR-001 数据契约 v1

> [方法选择｜C] 契约版本：`HD-DATA-CONTRACT-1.0`。
>
> [已观察事实｜A] 建立日期：2026-09-08（Asia/Shanghai）。
>
> [方法选择｜C] 状态：`CONTRACT_DEFINED_DATA_NOT_ACCEPTED`。本文件冻结“什么数据才算合格”，不表示当前已经拥有或验收了合格数据。
>
> [已观察事实｜A] 对应方法协议：[`HD-ANCHOR-001 v1.0-methods-frozen`](../experiments/HD-ANCHOR-001/preregistration.yaml)。
>
> [已观察事实｜A] 当前可见材料截止：标的风险快照至2026-09-04；分红候选说明至2026-09-03。尚未形成阶段5要求的只读原始数据包、清理后数据或`data_manifest.json`。
>
> [方法选择｜C] 本阶段不运行L0—L4实验，不查看策略收益或锁定测试结果，不授权仿真或真实交易。

## 1. 本阶段要回答的研究问题

[研究假设｜C] 只有价格、分红预期、公司行动和执行数据都具有明确的时间语义、来源、版本及可得性，才能判断HD-ANCHOR-001的结果来自当时可执行的信息，而不是复权误用、未来分红、事后成交价或成本遗漏。

[方法选择｜C] 本契约回答以下问题：

1. 每个字段代表什么、使用什么单位和数据类型；
2. 一个历史决策时点能够看到哪些记录；
3. 未复权价格、分红预期和真实现金分红如何分离；
4. 14:57代理Tick、信号、委托和最终竞价成交价如何分离；
5. 数据缺失、修订、冲突和过期时是否允许产生信号；
6. 原始数据如何保持只读，清理过程如何留痕并形成可复现版本；
7. 当前材料最多允许进入哪个证据等级。

## 2. 需要理解的理论、公式和时间语义

### 2.1 五种时间不得混用

| 时间 | [方法选择｜C] 定义 | 典型用途 |
|---|---|---|
| `event_time` | 经济或公司事件实际发生的时间；例如董事会形成方案、交易发生或权益事件生效 | 事件排序与审计 |
| `announcement_time` | 发行人或交易所正式发布文件的时间 | 判断公开披露先后 |
| `available_time` | 研究账户在不使用未来信息的前提下最早允许使用该记录的时间 | PIT连接的核心门槛 |
| `effective_time` | 该记录在业务上开始适用的时间 | 处理修订、除权和制度生效 |
| `retrieved_at` | 研究系统实际下载、接收或归档数据的时间 | 数据血缘和版本，不得替代历史可得时间 |

[方法选择｜C] 对任一决策时点`t`，只有同时满足下式的记录才可进入策略输入：

```text
available_time <= decision_time
effective_time <= decision_time
record_status = VALID
```

[方法选择｜C] `retrieved_at`晚于历史决策时间不等于数据不可用于历史研究；关键是来源文件能够证明该信息在当时已经公开。反过来，今天下载到的最终结果不能把`available_time`回填为更早日期。

### 2.2 股息率和价格锚

[方法选择｜C] 策略决策只使用当时有效的年度分红估计和未复权代理价格：

```text
forward_yield_t = expected_annual_dividend_per_share_t / proxy_price_t
anchor_price_t(r) = expected_annual_dividend_per_share_t / required_yield_r
```

[方法选择｜C] `proxy_price_t`是`[14:57:00,15:00:00)`内运行时序中首个合格Tick的`lastPrice`，不是15:00最终收盘价，也不是前复权或后复权价格。

### 2.3 分红预期的180日有效期

[方法选择｜C] 冻结方法`ANNOUNCED_ANNUAL_TOTAL_V1`只接受当时最新正式公告中明确的最近一个完整会计年度税前每股现金分红总额。估计年龄按Asia/Shanghai自然日计算：

```text
estimate_age_days = date(decision_time) - date(as_of_time)
valid = 0 <= estimate_age_days <= 180
expired = estimate_age_days > 180
```

[方法选择｜C] `as_of_time`采用该完整年度估计的原始`available_time`。只有新的明确全年金额、正式修订或明确重申全年金额的公告才能更新；重复下载、股东会通过、除息或到账本身不刷新期限。

[方法选择｜C] 如果只有公告日期、没有可验证的公告时分秒，`available_time`统一设为该公告日期之后首个交易日09:30:00。若取得精确时间，则使用实际公开时间；14:57之后发布的记录不能用于当天决策。

[方法选择｜C] 缺失、过期、来源不明或无法解析日期时，不得把分红填0，也不得产生有效交易信号；实际持仓、现金、公司行动和每日净值仍继续记录。

### 2.4 真实分红和账户恒等式

[方法选择｜C] 分红预期只决定估值锚，真实现金分红只由公司行动表进入账户。未复权价格和现金分红必须配套使用，禁止同时使用含分红复权收益并再次记现金。

```text
V_t = Cash_t
    + Shares_t * RawClose_t
    + DividendReceivable_t
    - TaxLiability_t
```

[方法选择｜C] 股权登记日收盘持股决定权益；除息日确认应收股息；到账日把应收转为可用现金；税负及其递延扣收单独入账。到账只改变现金与应收的分类，不再次创造收益。

### 2.5 信号、委托和成交不得混用

```text
14:57后首个合格Tick.lastPrice
→ 形成proxy daily bar
→ 生成目标仓位
→ 前置风控
→ 1秒后提交一次保护限价委托
→ 15:00最终竞价价只用于事后P00成交记账
```

[方法选择｜C] P00不使用最终竞价成交量、参与率或事后收益决定是否产生信号、是否发单或是否成交；也不另扣固定bp执行摩擦。佣金、最低佣金、印花税、过户费和其他实际费用仍须入账。

[已知限制｜C] P00“有效委托按最终竞价价假设全额成交”是研究模型，不是真实队列保证。P22/P23及L4必须另外检验未成交、部分成交和涨跌停队列风险。

## 3. 全局数据规范

### 3.1 标识、编码、时区和数值类型

| 项目 | [方法选择｜C] 统一规则 |
|---|---|
| 股票代码 | `600900.SH`；原始供应商代码另存`vendor_symbol`，不得覆盖规范代码 |
| 交易所 | `SSE` |
| 币种 | `CNY` |
| 时区 | 所有时间转换为`Asia/Shanghai`并保留原时区/原始文本；禁止无时区时间戳 |
| 日期 | ISO 8601 `YYYY-MM-DD` |
| 时间 | Parquet使用带时区`timestamp[ns]`；CSV使用含`+08:00`的ISO 8601字符串 |
| 价格/DPS | `decimal128(18,6)`；计算中禁止先降为两位小数 |
| 成交额/现金 | `decimal128(24,4)`；账户实际扣款按适用规则舍入后另存 |
| 股数/成交量 | 非负`int64`；未知为`null`，不得填0 |
| 布尔值 | `true/false/null`；未知不得写成`false` |
| 文本编码 | UTF-8；原始文件保留原编码并在清单登记 |

[方法选择｜C] 所有表至少包含`source`、`source_document`或`source_file`、`version`、`retrieved_at`、`raw_record_id`和`record_status`。清理后每行必须能够追溯到一条或多条原始记录。

### 3.2 来源优先级与双源核验

[方法选择｜C] 公司行动和分红金额的来源优先级为：上交所/巨潮法定披露或公司正式公告 > 中国结算/税务或财政官方规则 > 经许可行情供应商 > 独立财经数据库 > 新闻转载。

[方法选择｜C] 每个关键价格、DPS金额和公司行动日期原则上由两个独立来源核验：

- 数值相对差`<=1%`可采用主来源，并保存两源值；
- 数值相对差`>1%`标记`SOURCE_CONFLICT`并暂停进入正式数据；
- 日期、股票代码、除权日、到账日等离散字段必须完全一致，否则直接隔离；
- 日线OHLC原则上应完全一致或只存在供应商显示精度差；价格相差超过一个最小价位即进入人工复核，即使相对差未到1%；
- 两个二手来源与法定原文冲突时，以可验证的法定原文为准，并记录二手来源错误。

[已知限制｜C] 单一来源的历史Tick可能无法逐笔双源核验。此时必须以同日日线收盘、交易日历和公司行动做边界检查，并把证据等级降为B；不能标记为双源一致。

### 3.3 原始数据、规范化数据和派生数据

[方法选择｜C] 三层数据不得混写：

```text
raw/        原始响应或原始导出，只读、按字节哈希
staging/    字段映射、类型转换和候选冲突记录
cleaned/    通过契约与审计的规范化表
derived/    PIT日历展开、边界、信号、账户和结果
```

[方法选择｜C] 原始文件一经登记不得原地编辑、覆盖或补行。供应商修订必须作为新`version`和新文件进入；清理脚本以输入哈希和规则版本产生新输出。

## 4. A类：未复权价格数据契约

### 4.1 必需字段

| 字段 | 类型/单位 | [方法选择｜C] 语义与约束 |
|---|---|---|
| `datetime` | timestamp +08:00 | 日线对应交易所正式收盘时刻；与`session_date`一致 |
| `session_date` | date | 上交所交易日 |
| `symbol` | string | 必须为`600900.SH` |
| `vendor_symbol` | string | 供应商原始代码 |
| `open` | decimal CNY/股 | 未复权首笔/官方开盘价，正数或在停牌规则下为空 |
| `high` | decimal CNY/股 | 未复权最高价 |
| `low` | decimal CNY/股 | 未复权最低价 |
| `close` | decimal CNY/股 | 未复权正式收盘价，用于账户市值和P00最终竞价价交叉检查 |
| `volume` | int64 股 | 成交股数；若供应商使用手必须先按元数据转换，原值另存 |
| `amount` | decimal CNY | 成交金额，非负 |
| `pre_close` | decimal CNY/股 | 供应商定义的前收盘字段；不得默认等于上一行`close` |
| `previous_raw_close` | decimal CNY/股 | 由上一有效交易日未复权`close`派生，供审计 |
| `ex_reference_price` | decimal CNY/股/null | 交易所除权除息参考价，如能取得；不得覆盖`pre_close` |
| `trade_status` | enum | `TRADING/SUSPENDED/DELISTED/UNKNOWN` |
| `limit_up` | decimal CNY/股/null | 当日权威涨停价；无涨跌幅限制须配合状态字段 |
| `limit_down` | decimal CNY/股/null | 当日权威跌停价 |
| `has_price_limit` | bool | 是否适用涨跌幅限制 |
| `adjustment` | enum | 清理后正式表必须为`NONE` |
| `currency` | string | `CNY` |
| `source` | string | 供应商/交易所名称 |
| `source_document` | string/null | 接口、文件或文档定位 |
| `version` | string | 供应商版本或研究快照版本 |
| `retrieved_at` | timestamp | 实际取得时间 |
| `raw_record_id` | string | 原文件哈希＋原始行号/记录键 |
| `record_status` | enum | `VALID/QUARANTINED/SUPERSEDED` |

### 4.2 主键、约束与禁止事项

[方法选择｜C] 清理后唯一键为`(symbol, session_date)`。原始层允许重复，但必须保留供应商修订顺序；规范层只能有一条`VALID`记录。

[方法选择｜C] 有交易记录时必须满足：

```text
low <= open <= high
low <= close <= high
open, high, low, close > 0
volume >= 0
amount >= 0
```

[方法选择｜C] `volume=0`不能自动解释为停牌；停牌、缺失和真实零成交必须由`trade_status`及交易日历共同判断。缺关键OHLC或状态不明时不得产生信号或成交。

[方法选择｜C] 未复权价格用于股息率、交易、除权日价格和账户市值。前复权/后复权列如为审计需要必须另表存放，并以`adjustment`显式标识；不得进入HD-ANCHOR-001账户或股息率公式。

## 5. B类：历史时点分红预期数据契约

### 5.1 必需字段

| 字段 | 类型/单位 | [方法选择｜C] 语义与约束 |
|---|---|---|
| `estimate_id` | string | 永久唯一记录ID |
| `symbol` | string | `600900.SH` |
| `event_time` | timestamp/date | 形成该方案的经济事件时间；未知可空，不得代替公告时间 |
| `announcement_time` | timestamp/null | 法定披露系统正式发布时间；只有日期时为空并保留`announcement_date` |
| `announcement_date` | date | 法定公告日期 |
| `available_time` | timestamp | 历史决策最早可用时间；不得为空 |
| `available_time_method` | enum | `EXACT_PUBLICATION_TIME/NEXT_TRADING_DAY_0930/OTHER_PREDECLARED` |
| `effective_time` | timestamp | 估计业务生效时间，通常不早于`available_time` |
| `as_of_time` | timestamp | 180日年龄起算点，等于原始有效估计的`available_time` |
| `expiry_time` | timestamp | 由180自然日规则确定的最后有效边界 |
| `fiscal_year` | int16 | 完整年度所属会计年度 |
| `expected_annual_dividend_per_share` | decimal CNY/股 | 税前完整年度DPS，允许明确的0，不允许未知填0 |
| `currency` | string | `CNY` |
| `tax_basis` | enum | `GROSS_PRETAX` |
| `estimate_method` | string | 固定为`ANNOUNCED_ANNUAL_TOTAL_V1` |
| `estimate_components` | string/JSON | 中期、末期等组成和去重说明 |
| `source` | string | 主来源 |
| `source_document` | string | 可定位公告URL/公告编号 |
| `source_document_sha256` | string/null | 保存原文时必填 |
| `secondary_source` | string/null | 独立核验来源 |
| `version` | string | 记录版本 |
| `supersedes_estimate_id` | string/null | 修订链 |
| `confidence` | enum | `A/B/C`，含义见来源核验规则 |
| `note` | string/null | 差异化分红、修订等说明 |
| `retrieved_at` | timestamp | 归档时间 |
| `raw_record_id` | string | 原始记录定位 |
| `record_status` | enum | `VALID/REVISED/WITHDRAWN/QUARANTINED` |

### 5.2 PIT选择算法

[方法选择｜C] 每个决策时点按以下固定顺序选择DPS：

1. 过滤`symbol`一致且`record_status=VALID`；
2. 过滤`available_time<=decision_time`和`effective_time<=decision_time`；
3. 按`available_time, version`排序，取当时最新有效版本；
4. 检查`estimate_method=ANNOUNCED_ANNUAL_TOTAL_V1`及来源完整；
5. 检查自然日年龄不超过180日；
6. 通过后才计算`D/P`；否则记录具体阻断码。

[方法选择｜C] 阻断码至少包括：`NO_ESTIMATE`、`NOT_YET_AVAILABLE`、`STALE_ESTIMATE`、`SOURCE_CONFLICT`、`INVALID_DATE`、`ZERO_DIVIDEND_BLOCK`、`METHOD_MISMATCH`。

[方法选择｜C] 同一年度中期与末期金额必须通过`estimate_components`去重。已经写成完整年度总额的公告不得再次加上中期金额；只公布中期金额且未明确完整年度总额时，不允许自行年化或推断全年值。

[方法选择｜C] 后来股东会通过或实施公告若未修订完整年度DPS，只能作为证据强化，不能生成新的`as_of_time`。未来最终派发金额不得回填更早信号。

### 5.3 当前候选材料的处理

[已观察事实｜B] 当前候选文件[`600900_expected_annual_dividend_per_share_2021_2026.md`](600900_expected_annual_dividend_per_share_2021_2026.md)列出六个完整年度DPS及多源核验，但逐条`available_time`仍为空，且正文按“持续使用至下一年度公告”描述。

[方法选择｜C] 该文件不能直接作为正式PIT表。阶段5必须从原公告重新生成记录：日期级公告采用下一交易日09:30可用，逐条计算180日到期，并把到期后至下一条合格公告之间的时段保留为`STALE_ESTIMATE`，不得无限期前向填充。

[计算结果｜C] 如果一年只有一次合格完整年度公告，粗略的理论有效覆盖约为`181/365≈49.6%`，明显低于冻结的80%覆盖门槛。精确交易日覆盖必须等交易日历和公告时间完成后复算；当前不能通过延长有效期或删除过期日来满足门槛。

## 6. C类：真实现金分红与公司行动数据契约

### 6.1 必需字段

| 字段 | 类型/单位 | [方法选择｜C] 语义与约束 |
|---|---|---|
| `action_id` | string | 永久唯一公司行动ID |
| `symbol` | string | `600900.SH` |
| `action_type` | enum | `CASH_DIVIDEND/STOCK_DIVIDEND/SPLIT/RIGHTS/OTHER` |
| `announcement_date` | date | 首次公告日期 |
| `announcement_time` | timestamp/null | 精确披露时间，如能取得 |
| `record_date` | date | 股权登记日 |
| `ex_date` | date | 除权除息日 |
| `pay_date` | date | 现金实际发放日 |
| `cash_dividend_per_share` | decimal CNY/股 | 符合该股份类别的税前实际获派金额 |
| `ex_reference_dividend_per_share` | decimal/null | 交易所计算除息参考价采用的摊薄金额；与实际获派额分开 |
| `eligible_share_class` | string | 适用股份类别及排除范围 |
| `distribution_is_differential` | bool | 是否差异化分红 |
| `entitlement_rule` | string | 登记日持股、特殊不参与股份等规则 |
| `tax_assumption` | string | 个人账户分档、暂不扣缴/递延扣缴方法的版本标识 |
| `tax_rule_version` | string | 历史税制版本 |
| `source` | string | 法定主来源 |
| `source_document` | string | 公告URL/编号 |
| `secondary_source` | string/null | 独立核验来源 |
| `version` | string | 行为记录版本 |
| `retrieved_at` | timestamp | 归档时间 |
| `raw_record_id` | string | 原始记录定位 |
| `record_status` | enum | `VALID/REVISED/WITHDRAWN/QUARANTINED` |

### 6.2 权益和税务台账规则

[方法选择｜C] 公司行动表只描述发行人事件；账户应另建逐批权益表，至少包含`lot_id`、买入日、卖出日、登记日持股、应收金额、到账金额、已扣税、递延税负和税负结清日。

[已观察事实｜A] 国家税务总局现有官方政策页面说明：公开市场个人持股超过1年，股息红利暂免个人所得税；持股1个月以内和1个月至1年采用不同计税比例，并可能在卖出时由券商/中国结算追补。[股息红利差别化个人所得税政策](https://www.chinatax.gov.cn/chinatax/n810341/n810765/n1465977/n1466017/c1967339/content.html)

[方法选择｜C] 本契约不把当前税率外推到全部历史。阶段5必须建立带`effective_start`、`effective_end`、持有期区间、应税比例、税率、扣缴时点和官方来源的历史税制表；没有核验时不得默认免税或0税负。

[已观察事实｜B] 当前候选资料指出2022年度存在实际获派DPS与除息参考摊薄DPS不同的差异化分红情形。正式公司行动表必须同时保存两个字段，不能用除息参考金额替代账户真实权益。

## 7. D类：执行数据契约

### 7.1 14:57候选Tick表

| 字段 | 类型/单位 | [方法选择｜C] 语义与约束 |
|---|---|---|
| `tick_id` | string | 唯一Tick ID |
| `symbol` | string | `600900.SH` |
| `session_date` | date | 交易日 |
| `exchange_time` | timestamp +08:00 | 供应商标注的交易所事件时间 |
| `receive_time` | timestamp +08:00 | 研究系统实际接收时间；历史回放不可伪造 |
| `sequence_no` | int64/null | 供应商序号 |
| `last_price` | decimal CNY/股 | Xtquant `lastPrice`的原始映射值，不替换为虚拟参考价 |
| `auction_virtual_reference_price` | decimal/null | 收盘集合竞价虚拟参考价格，如供应商提供 |
| `virtual_matched_volume` | int64/null | 仅供字段审计/L4，不是P00成交门槛 |
| `virtual_unmatched_volume` | int64/null | 同上 |
| `stock_status` | string/int | 原始状态；规范映射另存 |
| `is_suspended` | bool/null | 规范化停牌状态 |
| `pre_close` | decimal CNY/股 | Tick中的前收盘字段 |
| `limit_up` | decimal CNY/股/null | 当日权威涨停价 |
| `limit_down` | decimal CNY/股/null | 当日权威跌停价 |
| `source` | string | Xtquant版本/其他供应商 |
| `source_field_map_version` | string | 字段映射版本 |
| `retrieved_at` | timestamp | 接收/归档时间 |
| `raw_record_id` | string | 原始包定位 |
| `record_status` | enum | `VALID/QUARANTINED/DUPLICATE` |

[方法选择｜C] 合格候选Tick必须同时满足：`14:57:00<=exchange_time<15:00:00`、同一交易日、`0<=receive_time-exchange_time<=5秒`、证券状态可交易、未停牌、`last_price>0`。按运行时真实接收顺序选择第一条；同一接收时刻按供应商序号稳定排序。

[已知限制｜B] 如果历史数据没有真实`receive_time`，就无法精确复现“首个收到的Tick”和5秒新鲜度检查。不得把下载时间或回测运行时间冒充历史接收时间；若未来另立接收延迟模型，必须登记为实现偏离并重新冻结相关方法。

### 7.2 最终竞价结果表

| 字段 | 类型/单位 | [方法选择｜C] 语义与约束 |
|---|---|---|
| `session_date` | date | 交易日 |
| `symbol` | string | `600900.SH` |
| `auction_close_time` | timestamp | 正常为15:00交易所时刻 |
| `official_auction_price` | decimal CNY/股 | 权威收盘集合竞价成交价/正式收盘价 |
| `official_daily_close` | decimal CNY/股 | 与A类日线交叉核验 |
| `auction_volume` | int64/null | 可选，仅供执行审计和L4 |
| `trade_status_at_close` | enum | 收盘时交易状态 |
| `source`、`version`、`raw_record_id` | string | 来源和血缘 |

[方法选择｜C] `official_auction_price`只能在信号和委托时点之后用于P00成交记账，不能回流到代理日K、两日确认、目标仓位或前置风控。其与正式日线`close`相差超过一个最小价位时隔离复核。

### 7.3 P00执行派生表

[方法选择｜C] 为复现信号—订单—成交链，派生表至少包含：

```text
decision_time
tick_exchange_time
tick_receive_time
proxy_price
dividend_estimate_id
trigger_boundary
pre_trade_shares
ideal_band_shares
adjacent_target_shares
executable_target_shares
order_submit_time
order_side
order_qty
order_limit
fill_model_id
fill_time
fill_price
fill_qty
commission
stamp_tax
transfer_fee
other_fee
execution_friction
reject_reason
```

[方法选择｜C] `fill_model_id`固定为`AUCTION_MARKETABLE_LIMIT_ASSUMED_FULL_V1`：有效且按时到达的买单以涨停价、卖单以跌停价作为保护限价；证券可交易且存在权威最终竞价价时，P00假设全额成交。`execution_friction=0`，最终竞价量不参与成交判定。

[方法选择｜C] 真实委托、成交回报、废单和部分成交字段是L4证据；P00模型记录不能伪装成真实券商回报。

### 7.4 交易制度版本

[已观察事实｜A] 上交所2018年8月20日起对股票实施14:57—15:00收盘集合竞价。[2018年收盘机制公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml)

[已观察事实｜A] 2026年修订的现行交易规则继续规定股票14:57—15:00为收盘集合竞价，期间不可撤单，并说明集合竞价即时行情包含虚拟参考价格、虚拟匹配量和虚拟未匹配量。[上海证券交易所交易规则（2026年修订）](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)

[研究假设｜C] 因集合竞价阶段未持续产生普通成交，Xtquant在14:57后新Tick中的`lastPrice`可能仍是14:57前最后成交价，也可能有供应商特定映射。必须用原始字段说明、连续数日样例和15:00正式收盘交叉验证；不能把`lastPrice`名称直接解释为虚拟参考价。

[方法选择｜C] 执行表必须包含`exchange_rule_version`，按交易日选择当时生效规则。不能把2026年规则中的费率、价格限制或字段语义无条件回填至2018年。

## 8. 配套表：交易日历与成本制度

### 8.1 交易日历

[方法选择｜C] `exchange_calendar.parquet`至少包含：`session_date`、`exchange`、`is_trading_day`、`open_time`、`continuous_end_time`、`auction_start_time`、`auction_end_time`、`close_time`、`special_session`、`source`、`version`。缺失日必须能区分休市、停牌和数据缺口。

### 8.2 交易费用表

[方法选择｜C] `fee_schedule.parquet`至少包含：`fee_type`、`market`、`security_type`、`side`、`effective_start`、`effective_end`、`rate`、`minimum_cny`、`maximum_cny`、`included_in_broker_commission`、`rounding_rule`、`source_document`和`version`。

[已观察事实｜A] 用户提供的个人佣金输入为成交额万一、每个父委托最低5元，当前卖出印花税输入为万五；这些仍须与真实交割单核对是否已包含经手费、证管费或过户费。

[已观察事实｜A] 上交所官方收费页面显示现行A股竞价交易经手费按成交金额双向计收，并存在历史调整；财政部、税务总局公告说明证券交易印花税自2023-08-28减半征收。因此正式费用表必须按生效日期版本化，不能使用一个当前费率覆盖全样本。[上交所收费一览表](https://www.sse.com.cn/services/tradingservice/charge/ssecharge/)，[印花税减半公告](https://www.mof.gov.cn/caizhengshipin/caizhengxinwen2/202308/t20230828_3904230.htm)

[方法选择｜C] 若券商佣金已经包含规费，账户只能扣一次；不能在佣金外再次机械相加。无法核验的费用不得默认0，正式运行前应标`FEE_SCHEDULE_UNVERIFIED`并关闭执行门禁。

## 9. 文件、目录、版本与清单

### 9.1 建议目录

```text
research/topics/high_dividend_bond/datasets/
  raw/
    prices/<source>/<retrieval-id>/
    dividend_estimates/<source>/<retrieval-id>/
    corporate_actions/<source>/<retrieval-id>/
    execution/<source>/<retrieval-id>/
    rules/<authority>/<retrieval-id>/
  staging/
  cleaned/
  manifests/
  audits/
```

[方法选择｜C] 原始目录只追加不覆盖；每个`retrieval-id`使用UTC归档时间或不可变供应商批次号。文件名不承担版本证明，SHA-256才是身份依据。

### 9.2 阶段5必需输出

[方法选择｜C] 为兼容研究主任务，清理完成后在主题`datasets/`下提供：

- `cleaned_price.parquet`
- `point_in_time_dividend_estimates.parquet`
- `corporate_actions.parquet`
- `cleaned_auction_ticks.parquet`
- `auction_outcomes.parquet`
- `exchange_calendar.parquet`
- `fee_schedule.parquet`
- `cleaning_log.csv`
- `data_manifest.json`
- `data_audit_report.md`

[方法选择｜C] `cleaning_log.csv`至少记录：`log_id`、输入文件哈希、表名、主键、字段、原值、新值、操作类型、原因码、证据、脚本版本、时间和执行者。任何删除、修改、填补、去重或隔离都必须有记录。

[方法选择｜C] `data_manifest.json`至少记录：契约版本、所有原始和清理后文件路径、字节数、SHA-256、来源、获取时间、覆盖日期、行数、唯一键、缺失率、隔离数、清理脚本哈希、Python/库版本、时区、数据许可限制和生成命令。

## 10. 数据验收测试

### 10.1 通用测试

[方法选择｜C] 每张表必须通过：schema、类型、主键、排序、时区、枚举、空值、来源、版本和血缘测试。未知值保持`null`并产生原因码；禁止为了通过测试填0。

### 10.2 价格测试

[方法选择｜C] 检查重复、交易日历、OHLC、正价格、非负量额、停牌、异常涨跌、除权交叉验证、复权标记和两个来源差异。异常不能只按收益阈值删除，必须与公司行动和停复牌记录联查。

### 10.3 分红预期测试

[方法选择｜C] 对每条估计重演`available_time`、修订链和180日到期；随机抽取及全部边界日验证`available_time<=decision_time`；检查同年度中期/末期是否重复；输出有效、过期、缺失和冲突的交易日比例。

### 10.4 公司行动测试

[方法选择｜C] 核对公告日≤登记日≤除息/到账相关日期的业务逻辑，但不以通用排序强行覆盖公告中的特殊安排；检查每笔DPS、适用股份、差异化分红和税制版本；以未复权除息跳变做合理性核对而非机械等式删除。

### 10.5 执行测试

[方法选择｜C] 每个交易日验证候选Tick窗口、接收延迟、首条选择、状态、涨跌停价、提交时间、最终竞价价和正式收盘的一致性。最终竞价量可以缺失而不阻断P00，但不得因此被填造；L4需要时另设完整性门禁。

### 10.6 语义夹具

[方法选择｜C] 清理与回放实现至少通过以下人工夹具：

1. 日期级公告在下一交易日09:30前不可用、09:30后可用；
2. 年龄恰好180日有效，第181日阻断信号；
3. 14:56:59 Tick不能入选，14:57后首个合格Tick入选，15:00 Tick不能入选；
4. 14:57代理价触发，但15:00最终价不重算信号，只用于成交；
5. 最终竞价量无论大小都不改变P00成交假设；
6. 除息日使用未复权价格且只记一次应收股息；到账日不重复收益；
7. 停牌、无价格或无历史接收时间时不伪造成有效交易；
8. 2022差异化分红中实际获派DPS与除息参考DPS保持分离。

## 11. 当前数据盘点与缺口

| 数据 | 当前观察 | [已知限制｜证据] | 当前门禁 |
|---|---|---|---|
| 未复权日线 | 用户说明可从Xtquant取得；研究目录尚无正式导出、源文件哈希或字段映射 | B/C | 未验收 |
| PIT分红预期 | 有2021—2026候选说明和金额核验；缺逐条精确`available_time`，且旧的无限前向使用口径与180日规则冲突 | B | 未验收；预计覆盖不足80% |
| 公司行动 | 候选说明引用部分实施公告；没有规范化事件表、税制表和逐条哈希 | B/C | 未验收 |
| 历史14:57 Tick | 用户说明实时可取得14:57快照和15:00信息；未提供覆盖历史样本的Tick及真实接收时间 | C | 阻断主执行口径L2/L3 |
| 最终竞价价 | 日线`close`可能可作交叉来源；尚无正式字段映射和两源核验 | C | 未验收 |
| 最终竞价量 | 当前未提供 | C | 不阻断P00；仅影响执行审计/L4 |
| 历史费用 | 个人当前佣金信息已提供；完整历史费率与佣金包含关系未核验 | C | 阻断正式净收益 |
| 交易日历 | 尚无版本化文件 | C | 阻断日期转换、180日边界和回放 |
| 原始只读归档 | 尚未建立 | A | 阻断阶段5正式审计 |

[计算结果｜C] 在当前文件状态下，研究最多支持L0规则验证和准备L1机械回放；尚不满足L2经济有效性回测的数据门禁。该结论来自数据完整性，不是策略收益判断。

## 12. 本阶段实际操作

[已观察事实｜A] 已读取阶段0章程、阶段1规格、阶段3冻结预注册及现有分红候选材料的字段和可得性说明；没有运行策略或生成收益结果。

[已观察事实｜A] 已核对2026-09-08可访问的上交所现行交易规则、2018年收盘集合竞价制度起点、官方收费入口，以及税务/财政官方股息税和印花税资料；这些来源只用于契约和历史版本要求，没有直接填造完整历史费率表。

[已观察事实｜A] 24项登记实验位于[`preregistration.yaml`](../experiments/HD-ANCHOR-001/preregistration.yaml)的`experiment_budget.profiles`，ID为P00—P23；它们不是24个已运行结果。

## 13. 本阶段产物及保存路径

- [已观察事实｜A] `research/topics/high_dividend_bond/datasets/data_contract_v1.md`：本数据契约。
- [已观察事实｜A] `research/topics/high_dividend_bond/experiments/HD-ANCHOR-001/preregistration.yaml`：冻结方法与24项配置来源。
- [待办事项｜C] 阶段5的数据文件、清理脚本、日志、清单和审计报告尚未生成。

## 14. 验收标准

| 验收项 | 当前状态 |
|---|---|
| [计算结果｜A] A—D四类必需字段、类型、单位和时间语义 | 通过 |
| [计算结果｜A] PIT可得性、180日到期、修订与缺失规则 | 通过 |
| [计算结果｜A] 未复权价格和现金分红防重复规则 | 通过 |
| [计算结果｜A] 14:57信号与15:00成交的隔离规则 | 通过 |
| [计算结果｜A] P00无竞价量门槛、无固定5bp摩擦 | 通过 |
| [计算结果｜A] 原始只读、版本、哈希、清理日志及数据清单要求 | 通过 |
| [已知限制｜C] 合格实际数据是否存在 | 未通过，待提供和审计 |

## 15. 已发现的问题和证据等级

| 问题 | 类型与证据 | 研究影响 |
|---|---|---|
| 年度公告频率与180日有效期/80%覆盖门槛可能不兼容 | [计算结果/已知限制｜C] | 即使数据真实，主结果也可能只能“观察”；禁止事后延长有效期 |
| 现有分红候选缺精确`available_time` | [已观察事实｜B] | 必须采用下一交易日09:30规则或取得原始时间戳 |
| Xtquant收盘竞价阶段`lastPrice`语义未验收 | [研究假设｜C] | 可能是14:57前最后成交价；不得替换成虚拟参考价或最终收盘价 |
| 历史真实`receive_time`和14:57 Tick尚未提供 | [已知限制｜C] | 阻断主口径L2/L3；仅日线不能复现生产信号 |
| P00全额成交假设偏乐观 | [已知限制｜C] | 不阻断L2条件回测，但结果不能提升为L4执行证据 |
| 历史费用及佣金包含关系未核验 | [已知限制｜C] | 阻断正式净收益与账户对账 |
| 差异化分红存在两个不同DPS口径 | [已观察事实｜B] | 实际权益和除息参考价必须分表保存 |
| 当前没有只读原始副本和数据清单 | [已观察事实｜A] | 阻断阶段5验收和可复现数据版本 |

## 16. 是否允许进入下一阶段

[方法选择｜C] 阶段4的“数据契约定义”通过，可以准备阶段5；但阶段5实际清理尚未放行，因为原始数据位置和文件版本未提供。

[待办事项｜C] 为一次性开启阶段5，需要研究者批量提供或指出以下材料所在路径：

1. Xtquant导出的600900.SH未复权日线原始文件；
2. 可取得的历史14:57—15:00 Tick/快照及字段说明，尤其`exchange_time`与`receive_time`；
3. 15:00最终收盘/竞价结果文件；
4. 分红公告原文或现有下载目录，以及公司行动/分红实施记录；
5. 券商佣金说明或脱敏交割单，用于判断万一佣金包含哪些规费；
6. 已经使用或查看过的600900历史回测区间和最晚日期，用于污染登记。

[方法选择｜C] 若上述材料只有一部分，阶段5仍可先清理已有部分并输出缺口，不会把缺失值填造出来；没有历史PIT和14:57执行输入时，证据上限保持L0/L1。

## 17. 外部来源与检索记录

- [已观察事实｜A] 上海证券交易所，《上海证券交易所交易规则（2026年修订）》，检索日期2026-09-08；用于现行交易时段、不可撤单、即时行情内容和交易所时间语义。[官方页面](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)
- [已观察事实｜A] 上海证券交易所，2018年收盘交易机制调整，检索日期2026-09-08；用于制度起点。[官方公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml)
- [已观察事实｜A] 上海证券交易所收费一览表及2023年经手费调整资料，检索日期2026-09-08；用于费用表必须按生效日版本化的要求。[收费一览表](https://www.sse.com.cn/services/tradingservice/charge/ssecharge/)
- [已观察事实｜A] 财政部、税务总局，证券交易印花税减半资料，检索日期2026-09-08；用于历史印花税版本要求。[财政部页面](https://www.mof.gov.cn/caizhengshipin/caizhengxinwen2/202308/t20230828_3904230.htm)
- [已观察事实｜A] 国家税务总局，上市公司股息红利差别化个人所得税政策，检索日期2026-09-08；用于逐批持有期和递延扣税字段。[官方政策](https://www.chinatax.gov.cn/chinatax/n810341/n810765/n1465977/n1466017/c1967339/content.html)

