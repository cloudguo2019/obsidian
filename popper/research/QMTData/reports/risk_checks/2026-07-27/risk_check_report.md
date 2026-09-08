# Sartre 风险检查报告

检查结论：**允许启动（ALLOW）**

## 本次检查

- 生成时间：`2026-07-27T23:10:49+08:00`
- CLI mode：`simulate`
- 配置文件：`C:\quant\MiniQMT\sartre\sartre_core\config\etf_rotation_config.json`
- 配置文件哈希：`sha256:0a23a086b9f46e6555f51685fe0b579dcdc9613e06f01c80ec4047a041f36a8a`
- Config execution.env: `sim`
- Config execution.max_cash: `5000.0`
- Config qmt.account_id: `666637965217`
- 人工确认的最大资金：`5000.0`
- 人工确认的账户 ID：`666637965217`
- 人工确认的当前持仓：`{}`

## 已读取的配置文件

- `C:\quant\MiniQMT\sartre\sartre_core\config\etf_rotation_config.json`
- `C:\quant\MiniQMT\sartre\sartre_core\config\base_config.json`

## 检查结果

| 分类 | 检查项 | 状态 | 实际值 | 期望值 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 基础配置 | CLI 运行模式有效（mode_valid） | 通过（PASS） | simulate |  | CLI 参数 --mode 必须是 backtest、simulate 或 live 之一 |
| 运行环境 | 配置运行环境有效（execution.env） | 通过（PASS） | simulate |  | execution.env 必须是 backtest、simulate 或 live 之一 |
| 运行环境 | CLI 运行模式与配置一致（mode_matches_config） | 通过（PASS） | simulate | simulate | CLI 参数 --mode 必须与配置中的 execution.env 一致 |
| 运行环境 | 已配置策略 ID（execution.strategy_id_present） | 通过（PASS） | etf_rotation_core |  | 必须明确配置 execution.strategy_id |
| 运行环境 | 策略 ID 与人工确认一致（execution.strategy_id_expected） | 通过（PASS） | etf_rotation_core | etf_rotation_core | execution.strategy_id 必须与人工确认的策略 ID 一致 |
| 运行环境 | 资产类型与人工确认一致（execution.asset_type_expected） | 通过（PASS） | etf | etf | execution.asset_type 必须与人工确认的资产类型一致 |
| 资金限制 | 已明确配置最大资金（execution.max_cash_present） | 通过（PASS） | 5000.0 |  | 必须明确配置 execution.max_cash，不能依赖默认值 |
| 资金限制 | 最大资金与人工确认一致（execution.max_cash_expected） | 通过（PASS） | 5000.0 | 5000.0 | execution.max_cash 必须与人工确认的最大资金一致 |
| 资金限制 | 未使用禁止的默认资金值（forbidden_default_cash） | 通过（PASS） | 5000.0 | 不在 [100000.0] 中 | execution.max_cash 不能等于禁止使用的默认资金值 |
| 账户与终端 | 已配置 QMT 账户 ID（qmt.account_id_present） | 通过（PASS） | 666637965217 |  | 必须明确配置 qmt.account_id |
| 账户与终端 | 账户 ID 与人工确认一致（qmt.account_id_expected） | 通过（PASS） | 666637965217 | 666637965217 | qmt.account_id 必须与人工确认的实盘账户一致 |
| 账户与终端 | 已配置 QMT 账户类型（qmt.account_type_present） | 通过（PASS） | STOCK |  | 必须明确配置 qmt.account_type |
| 账户与终端 | 已配置 MiniQMT 路径（qmt.miniqmt_path_present） | 通过（PASS） | C:\quant\迅投极速策略交易系统交易终端 华泰证券QMT实盘\userdata_mini |  | 必须配置 qmt.miniqmt_path 或 qmt.trader_path |
| 账户与终端 | 已配置 xtquant Python 路径（qmt.xtquant_site_packages_present） | 通过（PASS） | C:\quant\迅投极速策略交易系统交易终端 华泰证券QMT实盘\bin.x64\Lib\site-packages |  | 必须配置 qmt.xtquant_site_packages |
| 策略风控参数 | 总仓位上限有效（risk.max_total_position_pct_range） | 通过（PASS） | 0.6 |  | risk.max_total_position_pct 必须在 (0, 1] 范围内 |
| 策略风控参数 | 单标的仓位上限有效（risk.max_symbol_position_pct_range） | 通过（PASS） | 0.2 |  | risk.max_symbol_position_pct 必须在 (0, 1] 范围内 |
| 策略风控参数 | 单标的仓位不超过总仓位（risk.symbol_not_above_total） | 通过（PASS） | 0.2 | <= 0.6 | risk.max_symbol_position_pct 不能超过 risk.max_total_position_pct |
| 策略风控参数 | 每手数量大于零（risk.lot_size_positive） | 通过（PASS） | 100.0 |  | risk.lot_size 必须大于 0 |
| 策略风控参数 | 最小价格变动单位大于零（risk.tick_size_positive） | 通过（PASS） | 0.001 |  | risk.tick_size 必须大于 0 |
| 策略风控参数 | 价格笼子比例不为负数（risk.price_cage_ratio_non_negative） | 通过（PASS） | 0.02 |  | risk.price_cage_ratio 不能小于 0 |
| 策略风控参数 | 每日最大开仓次数不为负数（risk.max_open_per_day_non_negative） | 通过（PASS） | 3.0 |  | risk.max_open_per_day 不能小于 0 |
| 策略风控参数 | 每日最大平仓次数不为负数（risk.max_close_per_day_non_negative） | 通过（PASS） | 3.0 |  | risk.max_close_per_day 不能小于 0 |

## 阻断项

- 无

## 人工复核

- [ ] 确认 qmt.account_id 是本次准备使用的实盘账户。
- [ ] 确认 execution.max_cash 是本次计划投入的最大资金。
- [ ] 确认 execution.env 与本次计划的下单模式一致。
- [ ] 确认 MiniQMT 路径指向本次计划使用的交易终端。
- [ ] 确认 QMT 查询到的当前持仓股份数与人工确认值一致。
- [ ] 启动实盘前，确认上方检查结论为“允许启动（ALLOW）”。
