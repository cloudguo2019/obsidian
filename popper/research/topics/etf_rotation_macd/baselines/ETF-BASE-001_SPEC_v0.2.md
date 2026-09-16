# ETF-BASE-001 工程规格修订：MiniQMT 为准

> 版本：v0.2  
> 核验日期：2026-09-16（Asia/Shanghai）  
> 阶段1；门禁未通过；证据上限 L0  
> 前版：[规格 v0.1](ETF-BASE-001_SPEC.md)。第1—3节未被本修订替换的工程规则仍适用；冲突时本修订优先。

## 1. 本轮确定项

[方法选择｜用户已确认] 以 MiniQMT 的 ETF 集合竞价管线为基线，初始资金5000元，执行资产上限5000元，严格采用 `close > MA20`，新买只在前5内选。原执行草案中的100万元、完整收盘后次日开盘、排除集合竞价及更改 adapter 权重语义的提议不再作为当前推荐。

[已观察事实｜A] 2026-09-16 重核 ETF core、MACD core 与 ETF 配置哈希，均与 v0.1 相同。工程根目录仍为 `C:/Users/cg/Desktop/Nietzsche/FINITUDE-1.4.2/sartre`；这是已定位快照，不等于本轮已核验生产会话或券商账户。

## 2. `entry:rank_fill` 不可达是什么意思

[已观察事实｜A] `etf_rotation_core.py:1664` 的 `_entry_rows()` 先限定 `rank_value <= buy_rank_top_n`，当前 top_n=5；`select_etf_portfolio()` 在该结果上遍历，再于第941行判断是否给候选标记 `entry:rank_fill`（rank>5）。因输入已经没有第6名以后，这个 else 分支无法触发。

[计算结果｜A] 假设前5中只有2只同时满足趋势、类别/group等约束，而第6名合格，现行策略不会为凑满3只新买第6名。已持有的第6名仍可能按前15保留规则留下，这是持仓保留，不是新买补位。

[方法选择] 研究以现行行为为准：不补写前5外补位、不删除外部工程的死分支。本轮只修订研究解释。

## 3. 排名与回测价格冲突的确切含义

| 环节 | 已观察输入/行为 | 问题 |
|---|---|---|
| 排名 | 直接从策略配置取 `data.period=1d`、`data.adjust=qfq` | 20/60窗口按日线观测计算 |
| 回测配置 | `backtest.period=1h`、`backtest.adjust=none` | 对外声明小时线未复权，与排名输入身份不同 |
| 默认回测入口 | 有目录时传入 `market_kline/csv/1d/qfq` | 实际来源又是日线前复权 |
| CSV 转换 | `legacy_csv_to_canonical()` 把1h/none传给 `normalize_canonical_bars()` | normalizer 直接覆盖 period/adjust 标签，保留原时间戳和OHLC；既不重采样，也不反复权 |

[已观察事实｜A] 权威定位：`run/run_etf_backtest.py:20,37`；`run/run_unified.py:582,590`；`sartre_core/data/data_feed.py:354,389`；`sartre_core/data/schemas.py:92`。

[计算结果｜A] 合成2根日线 qfq 的 L0 检查证明：传入1h/none后，标签变为1h/none，但2个日线日期和OHLC值完全不变。该结果证明转换语义，不证明某个未经运行的历史批次实际走过此入口。

[已知限制] 冲突不意味着“指标价与成交价必须完全相同”。指标使用连续复权价格、成交/现金账使用真实未复权价格可以合理并存；必须有明确的数据身份、复权映射与信息可得时间。不能把 qfq 数字改名为 none 就当作真实可交易价格，也不能把完整日收盘数据当作14:57已知数据。

## 4. MiniQMT 的价格与时序基准

[已观察事实｜A] 排名读取历史 `1d/qfq`；`miniqmt_market_account_mixin.py:168` 取得14:57之后、状态18且新鲜有效的原始 `lastPrice`；`etf_rotation_core.py:446` 删除当日/未来历史行，再追加当日 Tick 作为代理 close。MA、20/60日动量与20日波动使用这条组合序列，不使用当日15:00才完整的正式收盘。

[已观察事实｜A] 排名可从14:57开始等待，成功后当日只刷新一次；缺少合格输入时等待，提交不早于14:57:30。排名不保证恰在14:57:00完成，也不保证在14:57:30前完成。提交窗口为 `[14:57:30,15:00:00)`。

[已观察事实｜A] 提交时再次捕获新鲜 Tick。买单限价取涨停价、卖单取跌停价，`single_submit` 单次提交、不撤单重报；真实成交与成交价格应以回报为准。影子账户按提交阶段代理 Tick 立即成交只是 sim 近似，该 Tick 可能与排名时使用的 Tick 不同。

[已知限制｜A] Tick 追加函数未执行复权因子转换；只有历史 qfq 的锚点与当日真实价格兼容时，直接追加才连续。当前尚未验证缓存的复权锚点、分配日期和历史时点因子，因此这是待核风险，不是已经证明所有日子均错。

## 5. 更正换仓与目标缩放的适用范围

[已观察事实｜A] v0.1 中“MiniQMT只在满3只且有退出时延后新买”的表述过宽：该 helper 存在于普通批处理，并被通用/盘后路径调用；当前 `_run_closing_auction_pipeline()` 按 `config.symbols` 顺序逐标的生成信号、风控、执行，不调用 `_defer_buys_until_exits_clear()`，也不调用批处理 `_scale_portfolio_target_pct()`。

[方法选择] 当前集合竞价直接消费核心账户目标比例。默认每只20%，与通用 helper 裁剪后的结果恰好一致，但不能据此认定两条管线语义相同。研究复现必须保留当前管线顺序；“组合构建先保留持仓/决定退出”不等于“真实卖单先成交、卖出款已释放给买单”。

[已知限制｜A] 成交回报、可用现金刷新、在途冻结、未知ETF持仓、T+1可卖量与组合实际峰值须另做生命周期验证。风险层的百分比限量是单 symbol 算法，不能单凭配置断言完整账户始终满足组合总60%。本轮没有修改这些行为。

## 6. 5000元的准确语义

[已观察事实｜A] `miniqmt_portfolio_mixin.py:68` 对资产和现金分别应用固定5000上限；`miniqmt_market_account_mixin.py:437` 用其创建风控上下文。账户总资产5004时执行资产基数仍5000；总资产4900时基数4900。这不是无限制复利，也不是每次可投入5000并忽略仓位。

[计算结果｜A] 基数5000时每只目标金额1000、最多3只、名义总目标不超过3000。买入目标份数使用风控输入的**涨停限价**：`floor_to_100(int(资产基数 × target_pct / 涨停限价))`，还受可用现金与仓位限额约束。

[计算结果｜A] 合成例：代理 Tick=1元、买入涨停限价=1.1元时，1000元目标得到900份；若代理价10元、限价11元，则1000/11不足100份，目标取整为0，买入被阻止。这只是算法示例，不代表任一具体ETF当前涨跌停幅度或报价。

[已知限制｜A] 当前配置 env=sim，不据此把用户5000元描述解释为本轮已验证实盘交易。sim费用为佣金0.01%、ETF最低0.1元、无ETF印花税；真实适用券商费用未核验。公平研究采用同一账户与成本契约，不能照用 Backtrader 当前10万元/0.1%/免最低费设置。

## 7. L0 与下一门禁

[计算结果｜A] 标准库检查器本轮首次运行17/17通过：`Ran 17 tests in 0.185s; OK`。新增：标签覆盖但不转换数据、5000资产/现金上限、涨停限价整手数量、集合竞价不调用普通批处理缩放/延迟 helper。旧换仓 helper 测试改名以明确仅覆盖通用批处理。

[已知限制] 静态调用契约和合成风控检查不等于集合竞价成交或真实账户生命周期集成测试；Backtrader broker、逐日历史 Tick、复权锚点、实际费用、品种结算和账户对账仍未覆盖。

[待办事项] 单一下一门禁：完成 [执行契约草案 v0.2](ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.2.md) 的待核项，形成与 MiniQMT5000元集合竞价管线同语义的研究复现契约并补齐L0。无需再次询问已确定的5000元、MA20和权威路径；遇到必须改动经济/执行规则的选择再请求用户确认。

[方法选择] 保持阶段1；不进入阶段2，不做正式回测、锁定结果开启、仿真启动或实盘交易。

## 8. 本轮新增快照哈希（SHA-256）

```text
2197504AA74AD074B054A7F5D09447346CD95D8AE6516C0D2C296EA1C1BA4D64  sartre_core/adapters/miniqmt_portfolio_mixin.py
17EF7A04077B95ADA961A512D5049B491FBD3CE760CE86935A78C9F79C1B5653  sartre_core/adapters/miniqmt_market_account_mixin.py
2D6E57FDC1C600815CD767B0F079689A65F20947F247A37A9129D680DC403F9E  sartre_core/adapters/miniqmt_closing_auction_mixin.py
667F801AFB5E0F14B8E5F083C807D067A3B48D7362DB9E72F7BCED035293BAFD  sartre_core/adapters/miniqmt_stock_execution_mixin.py
3B7C593AED59F2646A335F07B91F2B07BAB33BDEE01FFA34E7275B6E7944AF62  sartre_core/data/schemas.py
FAE738496537F5A42FFDEEB4D23E4EE9017AA54ECFDCBD7F72056A81CD206C6A  sartre_core/data/data_feed.py
6AFE2D1F897576AD883B4CEC6AD0FEA849341B7E80257FC505A4D45FD18B4C26  sartre_risk/risk_manager.py
85F561537A5CB57D6785010998DA26640B3EAF12F1A349DA07F53F70DE23515A  run/run_etf_backtest.py
24FD56DF2E596EDA982AAD1D79DF1128FD6051B83E74A672A3DDAB402054A445  run/run_unified.py
```
