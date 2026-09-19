# CG ETF Rotation 项目记忆

> [已观察事实｜A] 记忆快照：2026-09-18（Asia/Shanghai）。Popper 根目录为 `C:/Users/cg/Desktop/Nietzsche/obsidian/popper`。
>
> [方法选择] 当前阶段：阶段0、阶段1已闭环；阶段2理论材料“接受并闭环”；阶段3预注册草稿v1.0完成，**待签署，未闭环**。草稿新增门槛尚未采用，项目实证证据仍L0。沿用章程v1.2、价格契约ETF-PRICE-001/v1.0、三项修订ETF-EXECUTION-REPAIRS-001/v1.0及阶段1合并基线v1.0。本轮只读核验阶段1的51数据输入/12工程来源及阶段2的11本地artifact，三核心哈希未变；最近68/68机械验收为继承记录，无新策略测试。历史5反例仍保留：修复3项、用户接受2项时钟限制。正式回测/锁定开启/仿真/实盘执行与授权均0，FINITUDE未改。
>
> [待办事项] 单一下一工作门禁：用户签署[阶段3预注册草稿v1.0](experiments/ETF-REGIME-001/PHASE3_PREREGISTRATION_REVIEW_v1.0.md)。提案：净OOS ΔCalmar≥0.10、配对95%区间、共同78根支持、ENTRY只改新建仓、原生实际平均/峰值仓位差≤2/3pp；5账户×7场景=35单元/样本批次。15项运行绑定身份仍未建立，null不代表默认值；先签设计，后续依赖与精确批次另验收/授权。原八日工程资料接触已登记，2026档案保留段不称最终完全未触碰锁，最终锁拟前瞻12月、具体身份未建立。两项时钟接受不重开；v0.4整包不采用，不默认现金收益0、L1近似或正式批次授权。

本文是新对话的冷启动索引，不是独立证据。若本文与代码、配置、数据或清单冲突，以最小权威 artifact 集合为准，核验后更新本文。

[已观察事实｜A] 个人技能安装于 `C:/Users/cg/.codex/skills/cg-etf-rotation/`，界面名称为 `CG ETF Rotation`，显式调用写作 `$cg-etf-rotation`，并允许在明确提到 ETF 轮动项目或实验编号时自动发现。

## 一、新对话最小读取集

1. 每次先完整读取本文，再读取 [README](README.md)。
2. 只在重建方法或研究问题时，读取仓库根目录 `PERSONAL_STRATEGY_RESEARCH_FRAMEWORK.md` 的第20—26节；不要默认加载高股息案例。
3. 阶段1读取当前定位到的 `etf_rotation_core.py`、`macd_core.py`、`etf_rotation_config.json` 和直接相关测试。若 `FINITUDE-1.4.2` 不再是当前版本，先重新定位并更新哈希。
4. 数据阶段先读取 [初始数据盘点](datasets/INITIAL_DATA_INVENTORY_2026-09-15.md)，再按任务定向读取 `research/QMTData`；禁止为冷启动遍历全部 2.1GB 数据和日志。
5. 涉及交易日时读取 `research/topics/trade_calendar/sse_trade_calendar_validation_20260909.md` 及其清单/数据；跨境 ETF、深交所或特殊品种不得未经核验直接沿用上交所日历。

冷启动后向用户报告：记忆日期、阶段/门禁、数据截止、证据上限，以及本轮准备读取的最小文件集合。

## 二、已核验工程快照

[已观察事实｜A] 当前定位到的可运行代码快照为：

`C:/Users/cg/Desktop/Nietzsche/FINITUDE-1.4.2/sartre`

该 `FINITUDE-1.4.2` 目录本身不是 Git 仓库。把它视为已定位的版本化快照，不把它自动等同于当前生产部署；若用户指出新版本或路径缺失，使用 `rg --files` 重新定位。

[已观察事实｜A] 2026-09-15核验、09-16重核、09-17闭环及09-18阶段3只读身份复核未变的关键文件：

| Artifact | SHA-256 |
|---|---|
| `sartre_core/strategies/etf_rotation_core.py` | `1F7006FC7240157840E928DD6EE1DFDC50868331F26A16506A31A1EE38884317` |
| `sartre_core/strategies/macd_core.py` | `C2199714C1DD3C848F72E6E05A67BB8F1788C8442AC5188CCBCFC4E84E8155E7` |
| `sartre_core/config/etf_rotation_config.json` | `8E14BC5BFEA0429158740E93308A6261BD2530429B4B697D8683770E2F6F355D` |

[已观察事实｜A] 当前 ETF 基线代码行为：

- 排名分数为 `(20日收益 + 60日收益 - 20日收益波动率) × 100`，三项权重当前均为1。
- 当前入场趋势条件在代码中是 `close > MA20`，并非“MA20 > MA60”；跌破 MA20 是持仓退出条件。
- 买入候选为排名前5；已持有 ETF 可保留至前15，但仍受趋势、缺失分数、同组更强替代和组合约束影响。
- 最多持有3只，单只目标/上限20%，组合上限60%，各 category 和 group 当前上限均为1。
- Backtrader 适配器在每个回测日期调用 `refresh_target_positions(..., as_of_date=current_date, skip_download=True)`，不是只使用期初目标；该行为仍需用小样本 L0 测试验证无前视和正确成交时序。
- 独立 `macd_core.py` 实现标准 `12/26/9` 金叉买入、死叉卖出；它尚未与 ETF 横截面排名和组合约束整合，不能直接替换 `strategy_id` 作为 ETF 轮动实验。

[已观察事实｜A] 阶段1形式化新增确认：设计文档中的双均线趋势与 `entry:rank_fill` 已过期；代码实际只用 `close > MA20`，且新买只来自前5。现有持仓先处理并按 symbol 字典序遍历。Backtrader 每个回测日动态刷新目标，但其 data feed 在期初固定，无法纳入期初池外的后来上市 ETF。

[已观察事实｜A] Backtrader 与 MiniQMT 执行不等价：Backtrader 有清仓信号就延后全部新买；MiniQMT普通批处理 helper 仅在满仓且有退出时延后新买。2026-09-16 更正：当前集合竞价管线不调用该helper或普通批处理权重缩放，而按config.symbols逐标的生成信号、风控和执行，不能套用普通批处理结论。Backtrader context 把全仓视为可卖，未单独模拟品种级结算。

[已观察事实｜A] 当前配置存在需要在阶段1/4解决的口径差异：排名数据配置为 `1d/qfq`，回测区块为 `1h/none` 且日期仅 `2026-01-01` 至 `2026-01-20`；运行入口在存在日线前复权 CSV 时又会传入该目录。执行环境配置为 `sim`，ETF 使用集合竞价管线，排名时点14:57、提交窗口14:57:30—15:00。研究不得据此默认各路径使用同一数据和成交口径。

[计算结果｜A] 2026-09-16 合成L0证明normalizer会覆盖period/adjust标签，却不转换时间戳与OHLC；默认入口可能把日线qfq标成小时线none，不能视为已获得真实成交价。MiniQMT历史qfq追加原始Tick时未做因子转换，复权锚点兼容性仍待核；尚未证明所有实际交易日存在断点。

[已观察事实｜A] MiniQMT的5000是执行资产/可用现金固定上限，不只是初始现金；资产超过5000仍以5000算目标，低于5000则以较低实际资产计算。集合竞价份数按委托限价（买涨停/卖跌停）换算并100份取整；每只20%是最多约1000元名义目标，不保证实际成交恰好20%。

[已观察事实/计算结果｜A] 本轮新增规格 `baselines/ETF-BASE-001_SPEC_v0.3.md`：context只含当前symbol，risk的60%是单symbol限量而非全账户剩余敞口；目标刷新会把目标文件symbols置于原config.symbols之前，零目标也在其中，不能假定卖单优先。真实pipeline＋离线回报夹具复现退出未成交时4只/78.00156%敞口；不是实盘结果。仅将SELL先提交仍不等待成交。新执行L0 15项11通过/4预期契约失败（账户caps、未来quote容忍、佣金预留、周六T+1解锁），新采集时钟L0 2项1通过/1预期契约失败。

[已观察事实｜A] `market_tick.capture_slot()`的captured_at在_fetch前记录；集合竞价event_time在逐symbol查询前采now且logger截为秒。captured_at是查询开始标记，不能映射为价格契约received_at，旧日志无法精确重建τ。纯内存2秒查询延迟L0证明quote领先开始标记不等于前视。权威解释为 `datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.1_2026-09-16.json`，替换v1.0解释但不覆盖旧结果。原价格原型仍严格quote≤received≤τ，数学12项通过不代表旧实时管线合约通过。

[已观察事实｜A] 成本配置也不一致：当前回测佣金为0.1%、滑点0.01%；影子账户基础配置为佣金万一、ETF最低0.1元且无印花税；Backtrader 对 ETF 当前使用比例佣金且免最低佣金。经济比较前必须冻结统一、现实且适用日期的成本模型。

## 三、已核验数据快照

[已观察事实｜A] 详细方法和哈希见 [初始数据盘点](datasets/INITIAL_DATA_INVENTORY_2026-09-15.md)。当前最重要的事实：

- `research/QMTData` 有2,871个文件、2,120,564,027字节；它是大型研究快照，不能在每次冷启动中全量扫描。
- ETF 行情有72只 `1d/qfq` CSV及对应72只 Parquet，整体覆盖 `2020-01-02` 至 `2026-09-09`；65只当前关注池标的全部有行情并更新到截止日，另7只非当前关注池文件停在 `2026-07-24`。
- 当前关注池65只且全部 enabled，分为 broad 6、industry 41、theme 18；这是当前人工池，不是2020年以来的历史时点 ETF 池。
- `universe_etf.csv` 有1,632行，其中1,576行 `as_of_date=2026-07-24`，56行日期空缺；不能单独重建历史池。
- 已归档的排名/目标输出快照只有15天（2026-07-15—2026-09-09）；simulate 日志目录46天（2026-07-14—2026-09-09），且各日志流并非每天齐全。
- ETF 行情目前只定位到前复权序列；尚未定位到覆盖研究期的真实未复权 ETF 成交价与现金分配序列。
- 本轮定位到 `data/market_tick/csv/` 原始Tick，23日期目录20260805—20260909；仅文件名库存，未全量审计。固定8日日志＋3symbol×8日案例（159201.SZ、510300.SH、510500.SH）有15840行；计划内8日各66个Tick文件，采集summary覆盖65symbol。此前未展开的Tick发现不补齐长期原价日线/因子/分配或历史池。
- 8日proxy捕获516次，其中261次quote领先event_time 1—3秒；案例15:00前1440行、285行quote领先查询开始标记、356行stale（含重复），不推断未来数据泄漏。计划内order10行是5 SUBMITTED＋5 SIMULATED_FILLED，均simulate，真实broker成交证据0；context13行均单symbol且无冻结现金/全账户市值。
- 当前配置4个SDK路径本机均不存在，随附Python未定位xtquant；只证明这些已检查路径/当前runtime，不能断言其他机器/安装均无SDK。哈希/路径检查见时钟修订v1.1。

## 四、研究身份与初始边界

[研究假设] 轮动排名回答“选谁”，趋势状态回答“是否可持有”，触发回答“何时行动”。MACD 应作为 ETF 轮动层中的状态或触发变量，而不是替代 ETF 池、横截面排名、类别/group限制和组合仓位。

[方法选择] 初始基准身份：

- `ETF-BASE-000`：风险匹配的被动或等权 ETF 组合；
- `ETF-BASE-001`：当前 MA 状态＋20/60日动量减波动排名＋现有组合约束；
- 第一个候选单变量实验为 `ETF-REGIME-001`：只将趋势状态替换为 `DIF > DEA`，MACD 固定 `12/26/9`，其余规则保持不变。

这些实验身份是研究起点，尚非阶段3预注册。首要指标“相对 `ETF-BASE-001`、同等组合敞口下的样本外 Calmar 改善”已于2026-09-15由用户确认，v1.1修订继续沿用。阶段2不改变该主指标，数值改善门槛/区间及公平匹配规则待阶段3冻结。

## 五、当前缺口与下一步

[已知限制｜A] 当前至少有五个阻止可信 L2 的缺口：

1. 历史时点 ETF 池、准入/退出和分类版本尚未建立，存在幸存者偏差。
2. 真实未复权成交价、ETF现金分配及复权因子处理尚未形成数据契约。
3. 排名 `1d/qfq`、回测 `1h/none`、入口 legacy CSV 与集合竞价信息集之间存在口径/时序待核。
4. 回测与影子账户的佣金、最低费用和滑点不同。
5. 尚无与当前代码、当前数据版本和公平基准对应的正式 ETF 回测结果或锁定样本。

[已观察事实｜A] 用户于 2026-09-15 明确回复“全部采用建议默认值”；`hypotheses/research_charter.md` 已冻结为 v1.0，确认发生在任何正式结果查看之前。阶段0完成并允许进入阶段1。

[计算结果｜A] 历史2026-09-16诊断：工程17/17（0.159s）、价格12/12（0.005s）、执行15项11通过/4预期契约失败（0.096s）、采集时钟2项1通过/1预期契约失败（0.008s），合计46项41通过/5反例；旧结果不覆盖。2026-09-17修复验收另为68/68，五项处置见闭环记录。unittest的OK(expected failures)不等于旧测试通过。pytest/backtrader依赖缺失，真实broker与完整生产生命周期仍未覆盖；随附Python3.12.14，-B，不安装依赖、不启动外部订单。

[已观察事实｜A] 当前观察规格是 `baselines/ETF-BASE-001_SPEC_v0.3.md`，继承v0.2/v0.1未替换规则；新增账户、查询顺序、时钟/结算/费用差异和反例。v0.4为研究保护提案尚未采用。5000元替换章程旧资金值，未改回测工程10万元设置。

[已观察事实｜A] 用户2026-09-16指定 `close > MA20`、MiniQMT为准、实际5000元。已另建 `hypotheses/research_charter_v1.1.md` 与 `baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.2.md`，保留冻结v1.0与旧草案。旧草案的100万元、完整收盘后次日开盘及集合竞价不作基线等提议不再是当前推荐；新方向不等于全项契约或正式批次授权。

[方法选择｜本轮用户已确认] 用户回复“按照你的建议执行，并查看阶段0是否闭环”。已冻结 `baselines/ETF-PRICE-001_CONTRACT_v1.0.md`：实盘目标/回测信号统一front_ratio，执行/现金账统一原价；当日锚定，Tick因子比F_t/F_t=1，历史用已生效且τ已知事件重基；τ记录实际接收截止，不倒灌稍后行情。标准库研究原型 `baselines/etf_price_contract_v1.py` 已实现并通过合成L0。SDK复权对Tick无效、区分front与front_ratio及除权接口来源为迅投官方文档（https://dict.thinktrader.net/nativeApi/xtdata.html）；SDK字段与研究累计F/事件乘数映射尚未核验。旧设计note保留为提议历史。

[已观察事实｜A] 当前合并章程 `hypotheses/research_charter_v1.2.md`、执行草案 `baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.3.md`、验收 `decisions/PHASE-0_CLOSURE_2026-09-16.md` 已建立；阶段0逐项通过，无额外个人确认，判定“接受”仅限章程验收，不是接受策略。价格切换是已登记研究修订，不把旧工程snapshot的qfq自动称为front_ratio；未修改冻结旧文件、运行工程、README或原始数据，未部署/交易、未增加任何正式授权。

[方法选择] 阶段1门禁现已通过：三项研究修复L0验收＋两项用户接受的秒级时钟限制，当前范围为工程形式化；允许阶段2理论与证伪。供应商事件/方向/锚点、真实front_ratio、历史池/原价/分配、broker在途现金/结算/完整回报、真实费用/日历与现金收益留作后续数据/正式实验依赖。必要L1近似或新增经济规则仍需确认，正式/锁定/仿真/实盘不许可。

[已观察事实｜A] 本轮权威归档：`decisions/PHASE1_REVIEW_2026-09-16_v1.0.md`、`datasets/PHASE1_READONLY_PLAN_v1.0_2026-09-16.json`、`datasets/PHASE1_READONLY_AUDIT_v1.0_2026-09-16.json`（51输入哈希）、`datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.1_2026-09-16.json`、`decisions/PHASE1_EXECUTION_L0_v1.0_2026-09-16_attempt1.json`、`decisions/PHASE1_CAPTURE_CLOCK_L0_v1.0_2026-09-16.json`。脚本首次对positions按JSON解析失败，修为JSON/安全literal_eval后审计成功；原数据未改。失败契约保留，无正式结果查看/新授权/样本污染。

[计算结果｜A] 历史 `decisions/PHASE1_EVIDENCE_MANIFEST_v1.0_2026-09-16.json`：51数据输入、12工程文件、协议/脚本/文档身份验证；原快照离线反例4只、3900市值、4999.9资产、78.00156003%敞口。该清单和旧结果不覆盖；v0.4整包未采用，三项修复另见新修订；SDK/真实费率/原始数据仍待核验。新校验器 `scripts/validate_phase1_repairs_v1.py` 分开验证历史身份与三项修复，不把新增文件混入旧清单或改写旧计数。

[方法选择｜用户2026-09-17指令] 先登记方向与时钟解释于 `decisions/PHASE1_REPAIR_DIRECTIONS_AND_CLOCK_EXPLANATION_2026-09-17.md`；随后用户明确“上面3项你修复一下”，研究实现与验收完成；再明确第2/第5项时间可忽略并要求阶段1闭环。两项时钟现在接受为阶段1限制，不视为整包v0.4冻结或工程部署授权。

[已观察事实/计算结果｜A] 新修订 `baselines/ETF-EXECUTION-REPAIRS-001_v1.0.md`；实现 `baselines/etf_execution_repairs_v1.py`（完整账户BUY保护、显式费用、逐品种日历/批次锁定内存账本）与 `baselines/etf_execution_bridge_v1.py`（重载全账户的原引擎风控桥接）。未成交/部分退出不释放名额，确认全退才释放；在途BUY计入名额/敞口/目标/资金，broker冻结不双扣。不一律暂停安全BUY。以费用后保守权益和BUY限价检验60%总敞口/拟买symbol20%，整手边界可能减少一手。

[计算结果｜A] `tests/run_phase1_repairs_l0_v1.py`：39/39（0.022s），无expectedFailure；真实原集合竞价core/管线/请求/single_submit＋离线账户/路由，新账本。900现金/1元/最低0.1佣金改800份成功记账；周五买份周六不可卖、适用周一或合成休市后的周二释放，T0/T1混合按产品处理。原17工程/12价格回归通过。本轮首次31/39，7接口夹具错误＋1预期漏计佣金已修，首次结果/源文本保留，修夹具期间两实现未变。最终 `decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt2.json`；验收 `decisions/PHASE1_THREE_REPAIRS_ACCEPTANCE_2026-09-17_v1.0.md`；身份清单 `decisions/PHASE1_THREE_REPAIRS_MANIFEST_2026-09-17_v1.0.json`，校验原51输入/12工程及历史清单未变。

[已知限制] 新费用、日历、T0/T1规则是显式合成夹具，未证明真实券商/SH/SZ/跨境产品适用规则。内存账本不含分配/现金收益/完整经济模型、跨进程预留、重启回报恢复或SDK采集。完整性标记不能代替broker对账。原FINITUDE缺口仍在；时钟字段未修但已获阶段1限制接受。阶段1“接受”仅限工程形式化L0，不升级证据或授权。

[方法选择｜用户最新确认] 指令原文：“第二项和第五项中的时间可以忽略，因为我使用的是tick数据，3秒一个快照，同时策略是日线策略，这点不影响。把阶段1闭环”。已新增 `baselines/ETF-BASE-001_PHASE1_BASELINE_v1.0.md` 和 `decisions/PHASE1_CLOSURE_2026-09-17_v1.0.md`：三项修复、两项接受限制，阶段1“接受并闭环”。秒级影响无经济敏感性实验验证；3秒为快照节奏声明，不保证返回延迟；旧代码5秒容忍未改，captured_at继续表示查询开始。保留窗口、状态/陈旧检查、未来bar删除和复权事件as-of，不授权15:00完整收盘倒灌。

[计算结果｜A] `decisions/PHASE1_CLOSURE_MANIFEST_2026-09-17_v1.0.json` 汇总生效合并基线/闭环报告/接受指令/来源哈希/五项处置/门禁。`scripts/validate_phase1_closure_v1.py`只读校验，继承新39＋原17/12测试、原51输入/12工程及旧结果身份，本次闭环不重复测试。旧清单中的phase1_gate_passed=false是前次历史状态，不覆盖；新闭环清单为true。README与本文当前索引已更新；下一阶段允许理论与证伪，尚未执行。

## 六、下一次最小读取集

1. 完整读取本文及README；
2. 读取 `experiments/ETF-REGIME-001/PHASE3_PREREGISTRATION_REVIEW_v1.0.md`、`preregistration_draft_v1.0.json` 与 `decisions/PHASE3_REVIEW_2026-09-18_v1.0.md`；
3. 接受具体签署时读取章程v1.2、阶段1合并基线及技能protocol；签署另建冻结版、签署记录和清单，保留草稿，不把设计签署变成35单元正式授权；
4. 核验身份读 `decisions/PHASE3_MANIFEST_2026-09-18_v1.0.json`，运行 `scripts/validate_phase3_draft_v1.py`（默认只读）；理论/旧规格/价格/三修复只按直接需要补读；
5. 签署前不进入阶段4；进入数据阶段才读初始盘点和定向输入，不全扫日志/行情；
6. 旧章程末尾阶段1待办、旧false门禁与失败均属历史，不改写、不重开阶段0/1或重复修复两项接受时钟。

## 七、阶段2当前成果（2026-09-17）

[方法选择] 用户“继续etf轮动策略阶段2”已执行。理论材料 `hypotheses/ETF-ROTATION-THEORY_v1.0.md`、原始来源记录 `hypotheses/ETF-ROTATION-SOURCES_2026-09-17_v1.0.md`、闭环 `decisions/PHASE2_CLOSURE_2026-09-17_v1.0.md`、身份 `decisions/PHASE2_MANIFEST_2026-09-17_v1.0.json`。阶段2判定“接受”仅限理论完整性；没有MACD有效性接受结论，允许下一步起草阶段3。

[计算结果｜逻辑] DIF>DEA不等于DIF>0或绝对上涨；金叉是一次转换，持续状态可覆盖排名晚于金叉的入场，但经济增量未知。H1排名预测、H2趋势防守、H3状态相对MA净OOS Calmar（主问题）、H4状态相对新鲜交叉已配预测/失败方向；12类替代解释未实际排除。

[已观察事实｜A] 直接核验MACD核心使用ewm(span,adjust=False)、首值递推初始化、12/26/9及默认78根；ETF基线61根。共同支持/初始化建议与ENTRY-001相对REGIME-001只改新建仓触发是阶段3提案，未冻结、未改池或可运行工程。状态替换需覆盖旧MA硬退出和同组候选，否则成双过滤。

[已知限制] 4条原始研究（Jegadeesh/Titman、Moskowitz/Ooi/Pedersen、Hong/Lim/Stein、Sullivan/Timmermann/White）本轮仅页面/搜索摘要，部分open失败；外部文献B级机制背景不升级项目L0。公平敞口配对不能事后调OOS倍率或将收益缩放称真实5000元账户。仍无正式/锁定结果查看，授权均0；数据截止沿用2026-09-09，无本轮污染。

## 八、阶段3当前成果（2026-09-18）

[方法选择] 用户“继续etf轮动策略阶段3”已推进到可签署草稿：[审阅稿v1.0](experiments/ETF-REGIME-001/PHASE3_PREREGISTRATION_REVIEW_v1.0.md)、[机器协议](experiments/ETF-REGIME-001/preregistration_draft_v1.0.json)、[进度门禁](decisions/PHASE3_REVIEW_2026-09-18_v1.0.md)、[身份清单](decisions/PHASE3_MANIFEST_2026-09-18_v1.0.json)、`scripts/validate_phase3_draft_v1.py`。结构验收不等于阶段3闭环；草稿不是冻结协议。

[方法选择｜提案未采用] 五臂为BASE-000等权、BASE-001原61根、BASE-001-CS78主对照、REGIME-001主候选、ENTRY-001辅助。仅1项主H3；共同78根、全固定as-of前缀，前一期h用同尺度上个已完成日线。主Δ≥0.10；10k配对stationary bootstrap，20日平均块，10/40敏感性，95%区间下界均>0；平均/峰值敞口差≤2/3pp，未匹配至多观察，无缩放。收益损失≤2pp/年、参与≥80%，章程风险/换手/成本硬线继续生效。7场景含原生、2倍费、2倍不利滑点、延迟1/2机会、起点晚20日、起点成熟池；每样本批次35单元，未执行。未来phase4—7补齐15项依赖，实质改规则须新签修订。

[已知限制] 样本提案开发2020—2022、验证2023、2024—2025四个半年OOS折，2026-01-01—09-09仅档案保留段；既有8日工程资料已查看，历史OOS还需先前接触台账。最终锁拟冻结后前瞻12月，具体日期/清单/授权尚无。PIT池、长期原价/分配/供应商front_ratio、多年排名Tick、真实成本/现金收益/规则/成交对账未建立。原stationary bootstrap论文只核验搜索摘要，直接open403，来源B级；固定数字是项目方法选择。项目证据L0，无正式绩效读取或新样本污染。
