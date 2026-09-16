# ETF-BASE-001 当前工程规格与差异表

> 版本：v0.1  
> 核验日期：2026-09-15（Asia/Shanghai）  
> 阶段：阶段 1 — 工程形式化  
> 状态：当前行为已形式化；门禁未通过，禁止正式回测  
> 证据上限：L0（机械规则与契约测试）

## 1. 阶段问题

[方法选择] 本阶段只回答：`FINITUDE-1.4.2/sartre` 中的 `etf_rotation_core` 实际如何生成排名、目标组合和执行信号，各运行环境是否具有同一信息集与执行语义。

[已知限制] 本阶段不评价收益，不运行正式回测，不打开锁定结果，也不修改可运行 FINITUDE/Sartre 工程文件。

## 2. 权威快照

[已观察事实｜A] 工程根目录：

```text
C:/Users/cg/Desktop/Nietzsche/FINITUDE-1.4.2/sartre
```

| Artifact | SHA-256 |
|---|---|
| `sartre_core/strategies/etf_rotation_core.py` | `1F7006FC7240157840E928DD6EE1DFDC50868331F26A16506A31A1EE38884317` |
| `sartre_core/strategies/macd_core.py` | `C2199714C1DD3C848F72E6E05A67BB8F1788C8442AC5188CCBCFC4E84E8155E7` |
| `sartre_core/config/etf_rotation_config.json` | `8E14BC5BFEA0429158740E93308A6261BD2530429B4B697D8683770E2F6F355D` |

[方法选择] 对当前行为，以代码优先于配置、配置优先于描述性文档；但配置或文档冲突必须保留在差异表，不得静默修正。

## 3. 六层形式化规格

### 3.1 时点 ETF 池

[已观察事实｜A] 候选来源是人工 `interest_etf.csv` 与 `universe_etf.csv` 按 symbol 的交集；还要同时满足 interest enabled、universe eligibility、非 ST、非停牌、category 可识别，以及后续行情暖机要求。默认未知持仓 `liquidate_unknown_etf=false`，即不在排名池中的账户持仓不会被 ETF 核心主动清仓。

[已观察事实｜A] 默认指标暖机为 61 根 bar：

```text
required_bars = max(MA60, 20日收益所需21根, 60日收益所需61根, 20日波动所需21根) = 61
```

[已知限制｜A] 当前 interest pool 和 universe 都不是覆盖 2020 年以来的逐日成员事件库，因此历史运行仍是 `当前池回看/幸存者偏差未消除`。Backtrader 在期初按 `start_date` 生成 ranked symbols 并据此建立固定 data feeds；后续虽每日重算目标，却不会动态增加期初 data feed 之外的新上市 ETF。

### 3.2 排名数据与指标

[已观察事实｜A] `load_etf_rotation_params()` 对当前配置读取顶层 `data`，所以排名路径使用：

```text
period = 1d
adjust = qfq
start_time = 20200101
end_time = today
```

[已观察事实｜A] 对决策日 `t`，指标函数保留 `bar_date <= t` 的数据，使用当日最后一根 bar。缺少 bars、字段、暖机或有效分数时分别输出可审计的失败原因。

### 3.3 横截面排名

[计算结果｜A] 对 ETF `i` 在决策日 `t`：

```text
R20(i,t) = C(i,t) / C(i,t-20) - 1
R60(i,t) = C(i,t) / C(i,t-60) - 1
VOL20(i,t) = std_sample(pct_change(C), latest 20 observations)
SCORE(i,t) = 100 × [R20(i,t) + R60(i,t) - VOL20(i,t)]
```

波动率是 pandas 默认样本标准差，未年化。只要 score 非空就参加横截面排名，趋势不合格仍可占据名次。排序键依次为 `score` 降序、`priority` 降序、`symbol` 升序。

### 3.4 单标的趋势、入场与退出

[已观察事实｜A] 当前 MA 基线实际趋势状态为：

```text
trend_ok(i,t) = C(i,t) > MA20(i,t)
```

`MA60` 被计算和输出，但不参与 `trend_ok`。因此 `C > MA20` 且 `C < MA60` 仍允许入场。

[已观察事实｜A] 新入场必须同时满足：

```text
rank <= 5
AND trend_ok
AND score 非空
AND filter_reason 为空
```

当前 `_entry_rows()` 已把候选限定在前 5，故文档所述前 5 以外的 `entry:rank_fill` 在现行代码路径不可达。

[已观察事实｜A] 当前持仓按以下顺序检查退出：

1. `close < MA20`；
2. `trend_ok=false`（相等也会在此退出）；
3. 排名跌出前 15；
4. score 缺失；
5. 同 group 存在进入前 5、趋势有效且 score 更高的替代标的；
6. 保留后若违反组合约束则退出。

[已观察事实｜A] 现有持仓先于新标的处理，持仓集合按 symbol 字典序遍历；若多个现有持仓之间发生类别、group 或数量冲突，字典序较前者优先保留，不是按排名优先。

### 3.5 组合构建

[已观察事实｜A] 默认目标为：最多 3 只、每只目标和上限均 20%、总 ETF 上限 60%，五个 category 各最多 1 只、同 group 最多 1 只。现有持仓保留到排名前 15 构成排名迟滞；新标的只从前 5 进入。

[已观察事实｜A] Backtrader 和 MiniQMT 都再次把目标映射视为“组合内部权重”，归一化到 `risk.max_total_position_pct` 后再受单标的 20% 上限裁剪。默认等权 20% 参数下，1—3 只标的最终仍各为 20%，总仓位不超过 60%；若以后引入非等权目标，该二次缩放可能改变策略层给出的账户目标权重。

### 3.6 执行信号

[已观察事实｜A] 核心把目标映射转为：

- 未出现在目标映射：HOLD；
- 目标为 0 且有持仓：SELL 至 0；
- 无仓或低于目标超过 1 个百分点：BUY 至目标；
- 高于目标超过 1 个百分点且有可卖量：SELL 至目标；
- 其余：HOLD。

[已观察事实｜A] `risk.enable_t1=true` 时，执行风险层用 `available_volume` 限制卖出。MiniQMT/影子账户能提供可卖量；Backtrader context 直接令 `available_volume = position.size`，没有独立模拟 ETF 的品种级 T+0/T+1 状态。

## 4. 决策、提交与成交时序

### 4.1 实时/仿真集合竞价路径

[已观察事实｜A] 当前配置和代码规定：

```text
14:57:00          开始取得排名 Tick
14:57:00—14:57:30 用状态 18 的新鲜 Tick 重建当日排名与目标
14:57:30—15:00:00 单次提交集合竞价委托
```

排名 Tick 必须不早于 14:57、市场状态为 18、价格有效，默认最大年龄 30 秒；任一非停牌排名标的缺少合格 Tick 时，整池排名继续等待。目标未刷新成功时，集合竞价订单保持门禁关闭。

[已观察事实｜A] 执行阶段再次要求状态 18 和新鲜 Tick，默认执行 Tick 最大年龄为 5 秒。代理收盘价用于策略判断；买单限价取涨停价、卖单限价取跌停价；`single_submit` 不撤单重报。仿真影子账户按代理价直接视为成交，真实订单并不保证成交。

### 4.2 Backtrader 路径

[已观察事实｜A] `UnifiedBTStrategy.next()` 在每个数据日期先调用一次 `refresh_target_positions(as_of_date=current_date, skip_download=True)`，然后用含当前 bar 的 frame 生成信号。因此排名不是期初生成后静态持有。

[方法选择｜B] 当前信号使用完整的 `t` 日 bar，并通过 Backtrader market target order 提交；按 Backtrader 默认语义应在下一根 bar 执行。该成交语义本轮只做了代码契约检查，因当前可用 Python 环境未安装 `backtrader`，尚未做真实 broker 生命周期集成测试。

[已观察事实｜A] 任一持仓产生清仓信号时，Backtrader 会把当日所有 BUY 改成 HOLD，等待退出完成；MiniQMT 仅在现有持仓数已达到 `max_holdings` 且有退出时延后新买。因此两条路径的“先卖后买”行为并不等价。

## 5. 文档—配置—代码差异表

| 项目 | 文档/意图 | 配置 | 代码实际行为 | 阶段1结论 |
|---|---|---|---|---|
| 趋势入场 | `close > MA60 AND MA20 > MA60` | MA20/MA60 | 仅 `close > MA20` | 以代码为当前基线；文档过期 |
| 持仓趋势退出 | 跌破 MA60 | MA20/MA60 | 严格跌破 MA20；等于 MA20 时以 `trend_not_ok` 退出 | 以代码为当前基线；文档过期 |
| 排名补位 | 允许前5外 `rank_fill` | 前5/保留前15 | 新买只遍历前5，`rank_fill` 不可达 | 删除研究解释中的补位假设 |
| 回测目标 | 文档部分段落仍称读取静态目标池 | 指向 latest CSV | 期初准备一次，此后每个回测日动态重算 | 以动态日更为当前基线 |
| 历史池 | 全市场 universe + eligibility | 当前 interest/universe | 当前池回看；data feed 在期初固定 | 只能支持带污染标签的 L0/L1 |
| 排名价格 | 日线前复权 | `data=1d/qfq` | 排名函数确实读取 `1d/qfq` | 明确 |
| 回测价格 | 应与信号/成交契约分离 | `backtest=1h/none` | 默认 runner 又优先指向 `csv/1d/qfq`，转换时沿用 `1h/none` 标签 | 严重口径歧义，门禁未通过 |
| 集合竞价信息集 | 14:57 代理收盘后报单 | 排名14:57，提交14:57:30—15:00 | 使用状态18新鲜 Tick；仿真按代理价立即成交 | 与 Backtrader 不等价 |
| 换仓顺序 | 先卖后买 | 无单一配置 | Backtrader 有任一退出即延迟全部新买；MiniQMT 只在满仓时延迟 | 环境不一致，门禁未通过 |
| T+1 | 执行层处理 | `enable_t1=true` | 实时按 available volume；Backtrader 把全仓视为可卖 | 产品/环境不一致 |
| 目标权重 | 文档称账户目标仓位 | 策略层20%/总60%，risk同值 | adapter 视为内部权重再归一化；默认值下数值碰巧一致 | 非等权前必须统一语义 |
| 初始资金 | 章程冻结人民币100万元 | backtest 10万元；sim `max_cash=5000` | 各环境沿用自身配置 | 正式实验前必须统一 |
| 成本 | 应跨环境一致 | 回测佣金0.1%、滑点0.01% | Backtrader ETF 免最低费；影子账户佣金0.01%、最低0.1元、免印花税 | 正式实验前必须统一 |

## 6. L0 测试记录

[计算结果｜A] 研究侧检查器：`tests/run_etf_base_001_l0.py`。

第一次运行：11 项中 8 项通过，3 项因测试夹具问题失败（浮点精确比较、缺少上下文必填字段、实时配置测试未设置 symbol）；未观察到策略断言失败。修正夹具后增加两项环境差异契约，最终结果：

```text
Ran 13 tests in 0.076s
OK
```

覆盖：快照哈希、配置参数、趋势与 score、前5入场/前15保留、组合上限、目标容忍、T+1 可卖量、目标缩放、每日动态刷新、退出门禁、实时窗口、数据口径冲突、环境换仓差异、MACD 尚未集成。

[已知限制｜B] 工程自带 pytest 套件没有运行，因为本机没有已注册 Python，Codex 随附 Python 又未安装 `pytest` 和 `backtrader`。本轮改用标准库 `unittest` 直接调用同一工程代码；核心与适配器纯 Python 规则已执行，但真实 Backtrader broker 生命周期仍未覆盖。

## 7. 阶段1验收、问题与下一门禁

[已观察事实｜A] 规则、公式、排名迟滞、组合约束和当前信号逻辑已无描述歧义，最高支持 L0。

[已知限制｜A] 仍有四项阻止阶段1门禁通过：

1. 排名 `1d/qfq`、回测 `1h/none` 与默认 runner 的日线前复权目录互相冲突；
2. Backtrader 与 MiniQMT 的换仓延迟规则不同；
3. Backtrader 未形成按 ETF 品种区分的 T+0/T+1 可卖量模型，也未用真实依赖执行成交生命周期测试；
4. 研究章程的100万元资金基准与回测/仿真资金、成本配置尚未统一。

[待办事项] 单一下一门禁：在 Popper 研究层冻结一个跨环境一致的 `ETF-BASE-001` 研究执行契约，明确指标价、实际成交价、`t` 日信号的最早成交时点、换仓延迟、T+0/T+1、100万元资金和统一成本；随后为该契约补齐可执行 L0 集成测试。

[方法选择] 阶段2理论研究尚不许可；正式回测、锁定结果、仿真和实盘仍不许可。
