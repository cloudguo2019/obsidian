# ETF轮动初始工程与数据盘点（2026-09-15）

## 1. 定位与范围

[方法选择] 本报告服务于 `cg-etf-rotation` skill 的冷启动定制，只做文件级盘点、少量表头/首尾记录检查和直接代码核验；它不是完整数据质量审计，也不是回测结果。

[已观察事实｜A] 研究根目录：`C:/Users/cg/Desktop/Nietzsche/obsidian/popper/research/topics/etf_rotation_macd`。

[已观察事实｜A] 当前定位到的工程快照：`C:/Users/cg/Desktop/Nietzsche/FINITUDE-1.4.2/sartre`。框架文档中旧的 `../sartre_core/...` 相对链接在当前 Popper 目录下不能直接解析，应以重新定位到的工程文件为准。

## 2. 工程资产

| 文件 | 字节 | SHA-256 | 用途 |
|---|---:|---|---|
| `sartre_core/strategies/etf_rotation_core.py` | 85,682 | `1F7006FC7240157840E928DD6EE1DFDC50868331F26A16506A31A1EE38884317` | ETF池校验、指标、排名、组合目标与执行信号 |
| `sartre_core/strategies/macd_core.py` | 7,904 | `C2199714C1DD3C848F72E6E05A67BB8F1788C8442AC5188CCBCFC4E84E8155E7` | 独立MACD金叉/死叉策略 |
| `sartre_core/config/etf_rotation_config.json` | 3,019 | `8E14BC5BFEA0429158740E93308A6261BD2530429B4B697D8683770E2F6F355D` | ETF数据、风险、执行、回测和组合参数 |
| `research/QMTData/data/etf_universe/interest_etf.csv` | 9,875 | `6285EEFD43C39D8D3B084F81843A27B6E1D3E69790F9EFC4ABD759A3FA09ECE9` | 当前人工关注池 |
| `research/QMTData/data/etf_universe/universe_etf.csv` | 283,525 | `61ED6C5F6A891E42E6346A5D866F1190EF055F7425D1E669F54D5EFB2D48BC10` | 当前全市场ETF快照 |

[已观察事实｜A] `FINITUDE-1.4.2` 目录不是 Git 仓库，因此以上哈希是本次可复现身份；不能用不存在的 commit ID 代替。

## 3. 当前代码行为摘要

[已观察事实｜A] `etf_rotation_core.py` 当前计算：

```text
score = (1 × 20日收益 + 1 × 60日收益 - 1 × 20日收益率标准差) × 100
trend_ok = close > MA20
```

[已观察事实｜A] 当前组合规则为：前5名进入候选；持有保留到前15；跌破MA20退出；同group有更高分且进入前5的标的可触发替换；最多3只、单只20%、总仓位60%、每个category/group最多1只。

[已观察事实｜A] Backtrader 适配器在每个回测日期刷新目标组合，然后调用 `order_target_percent`。Backtrader 默认下一可用bar成交的具体行为、不同周期对齐和当日收盘是否提前可见，仍需阶段1用最小合成样本验证。

[已观察事实｜A] `macd_core.py` 的计算参数为12/26/9，规则是金叉买入、死叉卖出。该策略没有 ETF 横截面排名、category/group和组合目标逻辑。

## 4. 行情与标的池盘点

[已观察事实｜A] `research/QMTData`：2,871个文件，共2,120,564,027字节。

[已观察事实｜A] `data/market_kline/` 当前文件：

| 目录 | 文件数 | 字节 |
|---|---:|---:|
| `csv/1d/qfq` | 72 | 9,333,299 |
| `parquet/1d/qfq` | 72 | 4,057,941 |
| `csv/1d/none` | 1 | 493,240 |

唯一 `1d/none` 文件是高股息项目的 `600900.SH`，未定位到覆盖研究期的未复权 ETF 日线。

[已观察事实｜A] 72只前复权 ETF CSV 的结构为：

```text
datetime,symbol,period,open,high,low,close,volume,amount,openinterest,adjust,source,is_synthetic
```

全体最早日期为2020-01-02，最晚日期为2026-09-09；72只均至少60根bar，67只至少500根bar，`is_synthetic=True` 行数为0。起始年份分布：2020年33只、2021年20只、2022年7只、2023年5只、2024年4只、2025年3只。

[已观察事实｜A] 当前关注池65只全部有行情并更新到2026-09-09。另7个不在当前关注池的文件停在2026-07-24：`159338.SZ`、`159807.SZ`、`159909.SZ`、`510050.SH`、`510880.SH`、`512480.SH`、`512660.SH`。

[已观察事实｜A] 当前关注池的65只全部 enabled，`primary_theme` 分布为 broad 6、industry 41、theme 18。该分类只描述当前人工池，不代表历史时点分类。

[已观察事实｜A] `universe_etf.csv` 有1,632行：1,576行 `as_of_date=2026-07-24`，56行 `as_of_date` 为空。`DATA_QUALITY_NOTES.md` 记录 xtquant 上市日期哨兵值和14项覆盖；这要求上市日期进入正式数据审计。

## 5. 历史输出与仿真日志

[已观察事实｜A] `data/etf_universe/history/` 有15个日期目录，范围2026-07-15至2026-09-09，保存部分 ranked、selected、target-position 输出；这些不是覆盖2020年以来的完整点时ETF universe。

[已观察事实｜A] `logs/simulate/` 有46个日期目录，范围2026-07-14至2026-09-09。主要 ETF 日志流覆盖不齐：`etf_event.csv` 41天、`ranked_log.csv` 41天、`etf_signal.csv` 39天、`etf_context.csv` 38天、`etf_order.csv` 33天、`etf_position_log.csv` 31天、集合竞价和Tick日志各8天。

[已知限制｜A] 这些日志可用于L4前的执行诊断和局部案例复盘，但不能替代长期日度权益、完整成交配对、点时 universe 或正式历史基准。

## 6. 进入正式研究前的门禁

1. [待办事项] 建立历史时点 ETF 池或冻结并明确标注“当前池回看”的证据上限。
2. [待办事项] 定义复权指标价、真实成交价、估值价和ETF现金分配的统一数据契约。
3. [待办事项] 核验 `1d/qfq` 排名、`1h/none` 回测配置、legacy CSV入口和集合竞价14:57信息集的真实执行时序。
4. [待办事项] 统一回测、影子账户和未来仿真的佣金、最低费用、滑点、税费与现金收益口径。
5. [待办事项] 用合成数据验证每日动态排名、目标刷新、前5/前15滞回、退出先于进入、组合上限和T+1。

[方法选择] 在上述门禁完成前，只允许L0规则测试和明确标记的L1机械回看，不发布L2经济有效性结论。
