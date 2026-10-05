# ETF 轮动阶段4数据契约审阅稿 v0.2

> 2026-09-27（Asia/Shanghai）。状态：**待签署草稿、数据未验收**。本版更正 v0.1 对 14:57—15:00 规则起始时间的笼统表达，区分沪深交易所；v0.1 及其 SHA 留作审阅历史。适用于阶段3已签的五账户、七场景研究；不改写 `preregistration_v1.0.json`、原始数据或 FINITUDE。市场库存截止 2026-09-09，当前证据上限 L0。

## 1. 问题与优先级

[研究假设] 在真实历史时点候选池、当时可得的 14:57 信号、原价成交和完整现金账下，MACD 状态相对 MA 状态的净 OOS Calmar 是否改善。数据契约只确定**哪些记录可进入实验及如何解释**，不读取绩效。阶段3冻结协议、章程 v1.2、价格契约 v1.0、阶段1合并基线优先；若本稿要求改变其方法，先签署版本化预注册修订，不能把本稿直接当作已生效覆盖。

[方法选择｜待签署] 任何可用于正式批次的输入都须有来源、提取时点、原始文件 SHA-256、字段映射、适用起止、时区、供应商/券商版本、转换代码哈希、质量报告及父清单。原始快照只读；清洗/重基输出另存并保留父哈希。一个批次绑定唯一清单，不在运行后换源、补行或修改生效日期。

## 2. 必需表与主键

| 表 | 最低字段（均附 `source_id, version, available_time, raw_hash`） | 主键/解释 |
|---|---|---|
| `instrument` | `symbol, exchange, product_type, listing_date, delisting_date, fund_id, tracking_asset, currency` | `(symbol, valid_from)`；代码变更/合并须显式事件，上市日哨兵值为未知 |
| `universe_event` | `symbol, action(add/remove/update), effective_time, universe_event_time, universe_available_time, eligibility_reason, priority, category, group, enabled, source_snapshot` | `(symbol, universe_event_time, revision)`；分别保存人工关注池与市场产品池事件 |
| `daily_raw` | `symbol, bar_date, bar_time, available_time, open, high, low, close, volume, amount, trade_status, adjust=none, source, version` | `(symbol, bar_date, source_version)`；OHLC 为原价，量/额单位单列 |
| `tick_raw` | `symbol, quote_time, received_time, snapshot_slot, last_price, bid/ask prices and volumes, stock_status, last_trade_time, source, version` | `(symbol, quote_time, receipt_sequence)`；`captured_at` 若为请求开始时间须另存，不代称 received_time |
| `corporate_action` | `symbol, event_type, announcement_time, available_time, effective_date, ex_date, record_date, pay_date, cash_per_share, ratio_factor, factor_definition, revision` | `(symbol, event_id, revision)`；现金分配、拆并份额/除权因子分开 |
| `product_rule` | `symbol, exchange, valid_from, valid_to, lot_size, tick_size, settlement_rule, calendar_id, price_limit_rule, trading_session_rule, order_type, halt_rule` | `(symbol, valid_from)`；T+0/T+1 和时段不按代码前缀推断 |
| `calendar` | `calendar_id, session_date, open/close/auction windows, holiday_or_halt, source_version` | `(calendar_id, session_date)`；覆盖下一适用交易日与跨境相关市场 |
| `fee_cash` | `broker, account_class, product_type, valid_from/to, commission_rate, minimum_fee, other_fees, tax_rule, cash_product, yield_rate, accrual_rule, settlement_availability` | 有日期效力的券商/账户实值；0 收益也须有凭证 |
| `order_event` | `order_id, symbol, side, quantity, limit_price, target_time, submit_time, accept_time, fill_time, fill_qty, fill_price, fee, status, frozen_cash, available_qty` | `(order_id, event_sequence)`；保留拒绝、部分、撤销、失联、到期及重启恢复事件 |

[方法选择｜待签署] 所有时间戳用带时区的 Asia/Shanghai 原值和 UTC 规范值；`available_time` 指策略当时能读取到该版本的最早时点，不用文件生成日冒充历史可得日。修订/回补保留双时间轴：业务生效时间与首次可得时间。`null` 是未知或不适用并有原因码，不能自动当 0、正常交易或最近值。价格币种与份额变更必须明确。

## 3. 历史时点池及资格

[方法选择｜待签署] 决策 `τ` 的候选集合为：当时已可得的 `interest` 加入事件 ∩ 当时已可得的市场产品身份，并满足 `listing_date≤t<delisting_date`、当日可交易/非停牌、产品规则与日历已知、分类/优先级可得、共同 78 根有效信号观测。退出事件以其已可得的生效时间生效；未知历史加入日期不得从今天的 `interest_etf.csv` 回填。基金名称、category/group、priority 的历史修订独立保留；排名前先计算共同非趋势资格。退市、暂停、复牌、名称与代码变更都需形成事件。

[已知限制｜A] 现有 `interest_etf.csv` 是 65 只当前人工池（本轮定向检查为 SH 37/SZ 28）；`universe_etf.csv` 的样本行只有 2026-07-24 快照/部分日期空缺。二者不能重建 2020—2025 历史加入/移出及当时分类。当前池回看只能标为 `当前池回看/幸存者偏差未消除`，不得支撑干净 L2。

## 4. 五种价格/收益序列

1. **指标与排名**：原始 `none` 日线加截至 `τ` 已生效且已可得的除权事件，按已签价格契约构造逐日锚定 `front_ratio`；删去当日和未来完整日线，只追加在 `τ` 前可得的当日原价 Tick 代理 close。共同前缀从已核验的 2020-01-02 或更晚上市/来源首日开始，EMA 不滑窗重置。MACD 前一期 `h` 和当期 `h` 用同一重基前缀。
2. **委托与成交**：真实未复权价格、逐时刻有效价格限制、买卖盘口/成交与交易阶段；报单限价不是成交价。无真实盘口/队列或 broker 回报时必须声明填单近似及证据上限。
3. **逐日估值**：持仓份额乘当时真实未复权收盘价；停牌或无成交时由带原因的估值政策给出标记价格与不确定性，不以 0 或无风险现金替代。
4. **总收益与现金账**：`equity = cash_available + cash_frozen + receivable + Σ(quantity×raw_mark_price) − payable`，逐事件计入真实分配、手续费、现金产品收益和交收；信号 `front_ratio` 收益不得再作为账户分配入账。除息日价格下调与应收/到账日在账户上分别记账，核对份额基准与税费。
5. **诊断序列**：供应商 `front_ratio`、现存 `qfq`、完整日收盘只可用于复权映射/偏差诊断；不能替代当时 14:57 信号或原价成交。所有比较都记录锚点、事件完整性和供应商版本。

[方法选择｜待签署] 日线须验证 `(symbol,date)` 唯一、单调、OHLC 界限、正价、量额单位、日历/上市覆盖、修订、停牌/零量/陈旧及原价与因子交叉对账。缺 bar 不补零收益、不自动前填；信号缺失或状态不可判时停止新增/调整，已有仓位与失败退出照实留账。强制缺口进入质量报告并标记该交易日是否可计入共同样本。

## 5. 14:57 可得性、交易制度与队列

[方法选择｜待签署] 每个决策记录 `universe_cutoff, bar_cutoff, quote_time, received_time_or_bound, τ, rank_time, target_time, submit_time, exchange_accept_time, fill_time`。名义 14:57 开始排名、`[14:57:30,15:00)` 提交，信号不使用 `τ` 后事件或完整日收盘。既有两项秒级时钟限制按阶段1接受范围保留；若原始日志只有请求开始 `captured_at`，历史精确接收时点不可反推，须记录时间边界及 L2 可证性。报价状态异常、超过基线 30 秒最大年龄、交易时段不合、晚于目标生成的补录，拒绝用作新目标。

[已观察事实｜A] 收盘集合竞价**并非从 2026-07-06 才在所有 ETF 上开始**：[深交所 2006 年交易规则](https://www.szse.cn/disclosure/notice/t20060515_499577.html)将基金列入证券品种（2.2.1），规定证券 14:57—15:00 为收盘集合竞价（2.3.2），自 2006-07-01 施行；故本研究 2020—2025 深市 ETF 的一般竞价时段已属于该机制。[港交所 2022 年 ETF 北向交易 FAQ](https://www.hkex.com.hk/-/media/HKEX-Market/Mutual-Market/Stock-Connect/Reference-Materials/Inclusion-of-ETFs-in-Stock-Connect/Inclusion_of_ETFs_in_Stock_Connect_FAQ_Cn.pdf)也明确区分当时深市 ETF 有收盘集合竞价、沪市 ETF 没有。**2026-07-06 是沪市基金的切换日**：[上交所 2026 年交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)第 2.4.2 条及其[技术实施说明](https://www.sse.com.cn/services/tradingtech/development/c/10816505/files/8006a51174524e7cae832568b5e726a6.pdf)把沪市基金尾盘从连续竞价改为收盘集合竞价。故本研究历史样本不能把沪、深 ETF 按同一尾盘撮合方式回放；逐产品例外仍须核验。**冻结阶段3“历史 closing-auction opportunity”措辞须在读取绩效前签署按交易所/日期分段的修订。**

[方法选择｜修订提案、未生效] `session_rule(symbol,t)` 决定当日 14:57 后是连续竞价还是集合竞价；延迟场景的“下一机会”定义为该产品/日期的下一合法 `[14:57:30,15:00)` 提交窗口，不把历史连续竞价伪装为 15:00 一次撮合。每条延迟目标保留生成时的信号/池版本，按 symbol 先入先出、不得被新信号替换；处理时重新检查账户、停牌、结算、费用和价格限制。窗口错过、队列冲突、接收不明、部分成交、跨日未成交须有显式生命周期与失效原因。未核验真实撮合/盘口时，不设定默认“限价可成交”规则。

## 6. 费用、现金收益、交易规则及验收

[方法选择｜待签署] 五账户同用适用日的真实券商佣金及最低费、其他显性费、税费豁免、保守 BUY 预留、非零且可验证的基础不利滑点、现金产品/闲置现金收益口径。`FEE2` 倍增显性费，`SLIP2` 倍增基础增量不利滑点；基础值为零/未知则 `SLIP2` 无效。现有 Backtrader 0.1%/0.01% 与影子账户万一/最低 0.1 元是不同旧设置，不可挑一个作为真实默认。ETF 二级市场产品的 T+0/T+1、整手、最小价位、涨跌停/申报约束、SH/SZ 日历和跨境休市/溢折价信息要按有效日期绑定；交易所概述只能作候选映射，不能代替逐产品核验。[上交所 ETF FAQ](https://etf.sse.com.cn/fund/quertion/)说明股票 ETF 为 T+1，部分债券/黄金/跨境/货币 ETF 为 T+0，通常 100 份与 0.001 元报价单位。

[方法选择｜待签署] 阶段5进入清洗前先作来源/字段覆盖表；正式批次前逐项验收：PIT 事件覆盖开发至 OOS 每个决策日、原价/分配与 front_ratio 映射、逐日 14:57 可得记录、产品规则和交易所时段、实际成本与现金收益、成交/账户对账、全部 SHA 清单。每天核对现金、冻结/应收、持仓、订单、费用、分配及权益恒等式；未对平不能发布经济结果。

## 7. 当前来源映射与证据门禁

| 依赖 | 当前定向证据 | 当前状态/下一动作 |
|---|---|
| 历史 PIT 池 | 当前 65 池；全市场快照主要 2026-07-24 | **缺** 2020—2025 加入/移出/分类/priority 可得事件；先取得历史版本或可核验事件源 |
| 原价/因子/分配 | 72 只 ETF `1d/qfq`；`510300.SH` 样本表头 `adjust=qfq` | **缺** 覆盖全期的 `none` 日线、现金分配和供应商 `front_ratio` 映射；逐产品除息日交叉对账 |
| 14:57 历史 Tick | 当前 Tick 目录 2026-08-05—09-09；`510300.SH` 样本有 `quote_time` 与 `captured_at` | **缺** 2020—2025；`captured_at` 非收到时间，短期样本不能倒推多年 |
| 交易制度 | 深交所 2006 年规则；上交所 2026-07-06 改制；港交所 2022 年两市 ETF 比较 | **冲突** 全历史单一集合竞价填单；先签按交易所/日期分段修订，核验特殊产品 |
| 费用/现金/回报 | 旧模拟配置与 L0 合成费用夹具 | **缺** 适用券商费表、现金收益、真实回报/盘口；不得自动取零或旧默认 |
| 日历/结算 | 已有上交所日历只覆盖至 2026-09-09；L0 合成 T+0/T+1 | **缺** 完整逐产品历史与跨境日历、券商可卖份额对账 |

[方法选择] 当前阶段4门禁判定：**草稿可审阅，数据契约未冻结，进入阶段5清洗或正式 35 单元批次尚未许可**。按现有库存仅支持 L0；以后若另行授权“当前池/日收盘/近似填单”机械回看，其标签与上限为 L1，不能用于已签 H3 的 L2 经济接受。数据与交易制度缺口修复后，还须阶段5审计、阶段6样本身份、阶段7公平基准、研究实现和精确批次授权。

### 直接证据

- 本地：`datasets/INITIAL_DATA_INVENTORY_2026-09-15.md`、`datasets/PHASE1_READONLY_AUDIT_v1.0_2026-09-16.json`、`baselines/ETF-PRICE-001_CONTRACT_v1.0.md`、`baselines/ETF-BASE-001_PHASE1_BASELINE_v1.0.md`、`experiments/ETF-REGIME-001/preregistration_v1.0.json`；本轮仅抽查两份 universe 表、`510300.SH` 一份 qfq 日线及 2026-09-09 一份 Tick 的表头/前几行。
- 外部：[迅投 XtData 接口](https://dict.thinktrader.net/nativeApi/xtdata.html)区分 `front` 与 `front_ratio`，且复权参数对 Tick 无效；现存文件的 `qfq` 标签仍须核对采集映射。[深交所 2006 年规则](https://www.szse.cn/disclosure/notice/t20060515_499577.html)、[港交所 ETF FAQ](https://www.hkex.com.hk/-/media/HKEX-Market/Mutual-Market/Stock-Connect/Reference-Materials/Inclusion-of-ETFs-in-Stock-Connect/Inclusion_of_ETFs_in_Stock_Connect_FAQ_Cn.pdf)、[上交所交易规则（2026）](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)及[上交所技术说明](https://www.sse.com.cn/services/tradingtech/development/c/10816505/files/8006a51174524e7cae832568b5e726a6.pdf)支持沪深尾盘差异；[上交所 ETF FAQ](https://etf.sse.com.cn/fund/quertion/)支持产品规则概述。
