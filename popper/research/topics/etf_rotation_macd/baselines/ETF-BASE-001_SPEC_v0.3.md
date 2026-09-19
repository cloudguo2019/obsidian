# ETF-BASE-001 工程规格修订 v0.3：账户与采集时钟

> 2026-09-16（Asia/Shanghai）；阶段1；工程参照仍为 FINITUDE-1.4.2/sartre。  
> 继承 [v0.2](ETF-BASE-001_SPEC_v0.2.md) 及其未替换规则。当前合并章程 v1.2、价格契约 v1.0 不变。  
> 状态：只读诊断完成，阶段1门禁未通过，证据仍L0。

## 1. 本轮核验范围和身份

[已观察事实｜A] 三个核心文件及本轮相关 adapter/risk 文件哈希与已索引快照一致。新增核验的 gateway、order policy、router、shadow account、market_tick 和 logger 哈希见 [审计](../datasets/PHASE1_READONLY_AUDIT_v1.0_2026-09-16.json) 与 [时钟修订v1.1](../datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.1_2026-09-16.json)。未修改可运行工程、配置或原始数据。

[方法选择] 本轮遵循 [只读诊断计划](../datasets/PHASE1_READONLY_PLAN_v1.0_2026-09-16.json)：固定8个集合竞价归档日期；原始Tick案例取当前池symbol升序首2只SH、首1只SZ（159201.SZ、510300.SH、510500.SH），共24文件。此前探查过最近3日的日志行数/表头；选样规则与收益无关。本轮没有正式策略收益结果。

## 2. 新增代码事实

| 环节 | 当前代码事实 | 与研究契约的差异 |
|---|---|---|
| 全账户上下文 | `miniqmt_market_account_mixin.py:437` 的 `query_context()` 只把当前symbol放入positions；`_sync_context_with_market()`同样只同步该symbol | 无完整账户持仓、在途买单或分类状态，无法据此检验全账户上限 |
| 总仓位限制 | `RiskManager.check_and_adjust()` 把单symbol份数限制为资产×min(20%,60%)/委托价 | 该算法未扣其他symbol持仓，配置60%不等于账户级60%保护 |
| 换仓执行 | 集合竞价逐标的处理；`single_submit`不等待、不撤单；卖单受available_volume限制 | 提交卖单或目标为0不表示退出成交，不会自动阻止其他symbol新买 |
| 配置顺序 | `refresh_strategy_targets()` 先放目标文件symbols，再追加原配置symbols去重；目标文件保留行序，包含零目标 | 实际顺序是刷新后的config.symbols，不能假定原interest池顺序或所有卖出排在买入前 |
| 手续费预留 | 风控affordable_delta为`int(available_cash/price)`；shadow buy另要求gross+commission≤available_cash | 风控允许的订单仍可能因最低佣金被影子账户拒绝；真实费率仍未知 |
| 结算 | shadow的enable_t1是账户级开关；自然日期改变即解锁全部持仓 | 未按产品区分，也未核验下一交易日；周六也解锁的合成缺口被复现 |
| 排名时钟 | refresh先记录now，再查询整池Tick，并以旧now传market_data_as_of | 查询返回后的真正接收/决策截止未记录 |
| 采集时钟 | `market_tick.py:964`在`_fetch()`前记录captured_at；`_run_session()`传查询前now | captured_at是查询开始标记，不能映射为价格契约received_at |
| 提交时钟 | `_run_closing_auction_pipeline()`在循环前记录一次now；logger把event_time截为秒 | 后续symbol的event_time不是其收到Tick或实际提交的精确时间；执行函数会重新检查提交窗口 |
| 报价时间 | 旧排名和执行输入接受最多5秒的quote领先旧now | 与研究原型`quote_at≤received_at≤τ`不等价；应先补真实时钟，不能从日志领先直接推断前视 |

[已观察事实｜A：官方接口] XtAsset的cash是可用金额，另有frozen_cash、market_value、total_asset；XtPosition有can_use_volume、frozen_volume、on_road_volume。不能用当前context中的cash直接构造完整现金余额恒等式，须保留供应商字段语义并对账。[迅投交易接口](https://dict.thinktrader.net/nativeApi/xttrader.html)

## 3. L0结果和反例

[计算结果｜A] 旧工程17/17（0.159s）、价格12/12（0.005s）回归通过。新增 [执行检查器](../tests/run_phase1_execution_l0_v1.py) 15项：11通过、4项预期契约失败（0.096s）；新增 [采集时钟检查器](../tests/run_phase1_capture_clock_l0_v1.py) 2项：1通过、1项预期契约失败。合计46项：41通过、5个保留的契约反例。`unittest OK(expected failures)`仅表示诊断夹具按预期运行，**不是门禁通过**。

[计算结果｜A] 合成账户初始5000元，A/B/C各1000份、原价均1元、现金2000；目标A退出，B/C/D各20%。D按买涨停限价1.1元取整为900份。外部离线回报夹具让D成交原价1元、佣金0.1元，A卖单仍未成交：实际4只、持仓市值3900、资产4999.9，敞口`3900/4999.9≈78.00156%`。目标仍3只/60%。将A卖单先提交也保留4只的反例。原价/限价是假定数学输入，不是具体产品的历史涨跌停规则。

[已知限制] 上述pipeline执行真实core/context/risk/集合竞价/request builder和SingleSubmitPolicy，但替换了外部broker状态、router交接和日志接口；不是完整生产集成。它证明该合成状态未被当前局部风控拒绝，不证明归档实盘账户已发生78%敞口。

[计算结果｜A] 现金900元、原价1元时，旧风控允许900份；shadow额外佣金0.1元使该笔被拒绝且账户不变。采集查询延迟2秒的纯内存夹具记录captured_at=14:57:00、quote=14:57:02，证明报价领先开始标记可以由查询延迟产生。

## 4. 数据定位修订

[已观察事实｜A] `research/QMTData/data/market_tick/csv/`定位到23个日期目录，20260805—20260909；只做文件名库存，未全量内容审计。计划内8日各66个Tick文件；集合竞价日志/采集summary覆盖65symbol，不能把66直接当作ETF池规模。

[计算结果｜A] 8日集合竞价有516次proxy_close_captured：日志所记时刻均在提交窗口、状态18、价格为正、日志年龄不超过5秒；261次quote领先event_time 1—3秒。24个Tick文件15840行；按所记captured_at划分15:00前1440行，其中285行quote领先开始标记、356行标记stale。其余14400行在15:00后，14326行stale。stale含重复报价，不能直接等同不可交易；样本比例仅为案例统计。

[已观察事实｜A] 计划内归档order仅10行：5 SUBMITTED记录、5 SIMULATED_FILLED记录，均simulate，真实broker成交证据0。context共13行，全部单symbol map，无frozen_cash和全账户market_value字段，不能据此完成账户/分配对账。

[已知限制] 初始审计v1.0的`future_quote`计数只表示两个已存时间字段的负差，`first_usable_capture_time`只是开始标记筛查；其可得时间解释由时钟修订v1.1替换。不得用该字段伪造真实received_at或τ。原始Tick存在不等于长期原价日线、已核验因子和14:57决策信息集齐全。

## 5. 阶段结论

[方法选择] 判定 **修改**，仅限阶段1执行契约；没有评价或淘汰MACD假设。当前规则已进一步形式化，但账户、时间与结算契约存在可复现缺口，阶段1不闭环，阶段2不允许进入。

[待办事项] 下一项可审阅修订见 [执行契约草案v0.4](ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.4.md)。它仅提出研究层账户保护与时钟方案，未冻结、未采用到正式批次；供应商因子/原价/实际费用仍待输入，正式/锁定/仿真/实盘授权均0。
