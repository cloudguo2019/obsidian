# CG ETF Rotation 项目记忆

> [已观察事实｜A] 记忆快照：2026-09-16（Asia/Shanghai）。Popper 根目录为 `C:/Users/cg/Desktop/Nietzsche/obsidian/popper`。
>
> [方法选择] 当前阶段：阶段0已闭环，当前合并冻结章程v1.2（5000元、MiniQMT集合竞价、严格MA20、无前5外补位）及已确认价格契约ETF-PRICE-001/v1.0（front_ratio信号、none执行、当日锚定）。旧版保留。阶段1完整执行门禁仍未通过；证据L0，工程17/17＋价格12/12通过。正式回测/锁定开启/仿真授权/实盘授权均0。
>
> [待办事项] 单一下一门禁：完成 `baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.3.md` 的供应商因子/真实Tick与回报、完整账户生命周期与成本验收。价格偏好已确认，不再重问；只有必要新经济模型选择、数据缺失需L1近似或规则变更才再确认。阶段0无需补充个人确认，门禁通过前不进入阶段2或正式回测。

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

[已观察事实｜A] 2026-09-15 核验、2026-09-16 重核未变的关键文件：

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

[已观察事实｜A] 成本配置也不一致：当前回测佣金为0.1%、滑点0.01%；影子账户基础配置为佣金万一、ETF最低0.1元且无印花税；Backtrader 对 ETF 当前使用比例佣金且免最低佣金。经济比较前必须冻结统一、现实且适用日期的成本模型。

## 三、已核验数据快照

[已观察事实｜A] 详细方法和哈希见 [初始数据盘点](datasets/INITIAL_DATA_INVENTORY_2026-09-15.md)。当前最重要的事实：

- `research/QMTData` 有2,871个文件、2,120,564,027字节；它是大型研究快照，不能在每次冷启动中全量扫描。
- ETF 行情有72只 `1d/qfq` CSV及对应72只 Parquet，整体覆盖 `2020-01-02` 至 `2026-09-09`；65只当前关注池标的全部有行情并更新到截止日，另7只非当前关注池文件停在 `2026-07-24`。
- 当前关注池65只且全部 enabled，分为 broad 6、industry 41、theme 18；这是当前人工池，不是2020年以来的历史时点 ETF 池。
- `universe_etf.csv` 有1,632行，其中1,576行 `as_of_date=2026-07-24`，56行日期空缺；不能单独重建历史池。
- 已归档的排名/目标输出快照只有15天（2026-07-15—2026-09-09）；simulate 日志目录46天（2026-07-14—2026-09-09），且各日志流并非每天齐全。
- ETF 行情目前只定位到前复权序列；尚未定位到覆盖研究期的真实未复权 ETF 成交价与现金分配序列。

## 四、研究身份与初始边界

[研究假设] 轮动排名回答“选谁”，趋势状态回答“是否可持有”，触发回答“何时行动”。MACD 应作为 ETF 轮动层中的状态或触发变量，而不是替代 ETF 池、横截面排名、类别/group限制和组合仓位。

[方法选择] 初始基准身份：

- `ETF-BASE-000`：风险匹配的被动或等权 ETF 组合；
- `ETF-BASE-001`：当前 MA 状态＋20/60日动量减波动排名＋现有组合约束；
- 第一个候选单变量实验为 `ETF-REGIME-001`：只将趋势状态替换为 `DIF > DEA`，MACD 固定 `12/26/9`，其余规则保持不变。

这些实验身份是研究起点，尚非阶段3预注册。首要指标“相对 `ETF-BASE-001`、同等组合敞口下的样本外 Calmar 改善”已于2026-09-15由用户确认，v1.1修订继续沿用。

## 五、当前缺口与下一步

[已知限制｜A] 当前至少有五个阻止可信 L2 的缺口：

1. 历史时点 ETF 池、准入/退出和分类版本尚未建立，存在幸存者偏差。
2. 真实未复权成交价、ETF现金分配及复权因子处理尚未形成数据契约。
3. 排名 `1d/qfq`、回测 `1h/none`、入口 legacy CSV 与集合竞价信息集之间存在口径/时序待核。
4. 回测与影子账户的佣金、最低费用和滑点不同。
5. 尚无与当前代码、当前数据版本和公平基准对应的正式 ETF 回测结果或锁定样本。

[已观察事实｜A] 用户于 2026-09-15 明确回复“全部采用建议默认值”；`hypotheses/research_charter.md` 已冻结为 v1.0，确认发生在任何正式结果查看之前。阶段0完成并允许进入阶段1。

[计算结果｜A] 工程检查器 `tests/run_etf_base_001_l0.py`：2026-09-15最终13/13，首次11项有3项夹具错误（已修正）；2026-09-16增至17/17（0.185s），本轮回归17/17（0.109s）。新价格检查器 `tests/test_etf_price_contract_v1.py` 首次12/12（0.008s），合计29/29；覆盖原价/当日锚点、除息/多事件、未来信息排除、重复/缓存/时区/晚到与陈旧价门禁。pytest/backtrader依赖缺失，真实broker与完整账户生命周期仍未覆盖；使用随附Python3.12.14，PYTHONDONTWRITEBYTECODE=1，不安装依赖、不启动外部订单。

[已观察事实｜A] 当前规格是 `baselines/ETF-BASE-001_SPEC_v0.2.md`，继承v0.1未改动规则并更正MiniQMT普通批处理/集合竞价适用范围，登记新增9个工程哈希。价格标签、信息集和成本仍待统一；5000元替换100万元章程基准，但未修改回测工程的10万元设置。

[已观察事实｜A] 用户2026-09-16指定 `close > MA20`、MiniQMT为准、实际5000元。已另建 `hypotheses/research_charter_v1.1.md` 与 `baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.2.md`，保留冻结v1.0与旧草案。旧草案的100万元、完整收盘后次日开盘及集合竞价不作基线等提议不再是当前推荐；新方向不等于全项契约或正式批次授权。

[方法选择｜本轮用户已确认] 用户回复“按照你的建议执行，并查看阶段0是否闭环”。已冻结 `baselines/ETF-PRICE-001_CONTRACT_v1.0.md`：实盘目标/回测信号统一front_ratio，执行/现金账统一原价；当日锚定，Tick因子比F_t/F_t=1，历史用已生效且τ已知事件重基；τ记录实际接收截止，不倒灌稍后行情。标准库研究原型 `baselines/etf_price_contract_v1.py` 已实现并通过合成L0。SDK复权对Tick无效、区分front与front_ratio及除权接口来源为迅投官方文档（https://dict.thinktrader.net/nativeApi/xtdata.html）；SDK字段与研究累计F/事件乘数映射尚未核验。旧设计note保留为提议历史。

[已观察事实｜A] 当前合并章程 `hypotheses/research_charter_v1.2.md`、执行草案 `baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.3.md`、验收 `decisions/PHASE-0_CLOSURE_2026-09-16.md` 已建立；阶段0逐项通过，无额外个人确认，判定“接受”仅限章程验收，不是接受策略。价格切换是已登记研究修订，不把旧工程snapshot的qfq自动称为front_ratio；未修改冻结旧文件、运行工程、README或原始数据，未部署/交易、未增加任何正式授权。

[待办事项] 阶段1门禁未通过：核验供应商事件完整性/乘数方向/锚点与真实front_ratio对账、历史原价/14:57Tick/分配/回报、顺序/冻结现金/可卖量/全账户、真实费用和现金收益。合成L0不是供应商/生产端到端已验；缺数据时不假称精确复现，必要L1近似与经济/规则选择再问用户。这些不妨碍阶段0闭环。不得提前进入阶段2、正式回测或锁定开启。

## 六、下一次最小读取集

1. 完整读取本文；
2. 读取当前合并冻结 `hypotheses/research_charter_v1.2.md`；只有追溯确认链才补v1.0/v1.1；
3. 读取 `baselines/ETF-BASE-001_SPEC_v0.2.md`（需完整规则才补v0.1第3节）；
4. 读取 `baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.3.md` 与冻结 `baselines/ETF-PRICE-001_CONTRACT_v1.0.md`；旧草案和未确认note不再作为当前门禁；
5. 若继续价格实现，读 `baselines/etf_price_contract_v1.py`、`tests/test_etf_price_contract_v1.py`；需工程复核才读/执行 `tests/run_etf_base_001_l0.py`；
6. 只在需复核工程事实时，定向读取规格中引用的当前工程文件。
7. 若核查阶段0闭环，读取 `decisions/PHASE-0_CLOSURE_2026-09-16.md`；阶段0已通过，不把阶段1/后续数据问题当作缺少个人确认。
