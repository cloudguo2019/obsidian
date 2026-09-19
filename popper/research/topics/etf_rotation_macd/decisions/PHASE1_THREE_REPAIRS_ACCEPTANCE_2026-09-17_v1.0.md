# 阶段1三项修复验收 v1.0

> 2026-09-17，Popper研究层，最高证据L0。FINITUDE/Sartre快照未修改。

[方法选择] 依据用户“上面3项你修复一下”，实施[三项修订v1.0](../baselines/ETF-EXECUTION-REPAIRS-001_v1.0.md)。此前[修复方向和时钟解释](PHASE1_REPAIR_DIRECTIONS_AND_CLOCK_EXPLANATION_2026-09-17.md)作为确认链保留，不采纳整个v0.4草案。

## 问题、实现与结果

| 原问题 | 本轮行为 | 验收观察（合成L0） |
|---|---|---|
| 旧仓退出未成交却新买，4只/~78% | 每次BUY检查全账户正持仓及在途BUY，未成交SELL不释放；最多3只、总敞口60% | 买单先/卖单先均仅提交旧仓SELL，仍3只/60%；部分退出保留名额，确认全退后允许新买 |
| 900现金准许900份，佣金导致拒单 | 显式费用上界进入现金和保守敞口，按整手选最大增量 | 买800份，费用0.1、现金99.9；研究风控至账本成交成功 |
| 周五买入周六变可卖 | 每品种绑定适用日历，为每批T1份额记录下一交易日 | 周六可卖0，周一100；合成周一休市品种到周二才解锁；T0当日仍可卖 |

[已观察事实｜A] 新代码为[保护/账本](../baselines/etf_execution_repairs_v1.py)、[风控桥接](../baselines/etf_execution_bridge_v1.py)；[新脚本](../tests/run_phase1_repairs_l0_v1.py)调用原快照的ETF core、集合竞价管线、请求构建和SingleSubmitPolicy，账户和路由为确定性离线夹具。gateway若尝试wait/cancel会直接报错。没有启动SDK、外部账户、仿真进程或实际委托。

[计算结果｜A] 新测试39/39通过；原工程检查17/17（0.123s）、原价格检查12/12（0.003s）通过，本轮共68/68。新测试没有用expectedFailure隐藏失败。39项最终结果见[attempt2](PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt2.json)。这是修订实现的通过数，不能用它覆盖历史诊断46项/5项失败，也不表示原工程被修好。

[已观察事实｜A] 首次attempt1为31/39，7个错误来自测试夹具：StrategyContext缺少必传cash/available_cash、环境用了字符串而不是枚举、OrderState剩余量字段误写remaining_volume；1个失败为预期值忽略新买佣金（剩600元不能买600份＋0.1元，应500份）。修正夹具后实现未变，39/39。保留[首次结果](PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt1.json)及[首次源文本](PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt1_sources.json)，最终脚本/实现哈希见最终结果及[证据清单](PHASE1_THREE_REPAIRS_MANIFEST_2026-09-17_v1.0.json)。

## 方法选择与边界

[方法选择] 不一律暂停所有BUY；只在约束无法满足时阻止。broker已冻结现金不重复扣除，接收不明的BUY保留本地预留和名额。费用后保守分母使恰好20%/60%的整手候选可能再少一手，详见修订文档；未改变趋势与排名。

[已知限制] 费用、calendar_id、T0/T1和日期均是合成输入。真实券商费率/其他费用、真实逐品种交易日规则及全账户/在途订单SDK对账尚未核验。本轮账本为内存L0，不含跨进程预留、回报重启恢复、现金分配、现金收益和完整经济模型。没有收益曲线、业绩比较或任何策略有效性结论。

[待办事项] 未修两项时钟契约：`captured_at`在查询前采样，不能当received_at；旧报价相对查询开始的未来容忍需结合真正接收时间修复。阶段1整体门禁、供应商因子/数据/真实费用问题仍保留。

[方法选择] 判定：**接受**，仅限本轮三项研究实现的L0验收；阶段1整体仍为**修改**，不进入阶段2或正式回测。用户三项修复目标已完成，不再等待这些目标的重复确认。formal backtest / lock open / simulation / live授权计数均0；原价及因子缺口未提升证据上限，未查看锁定结果或污染正式样本。

## 复现

Python：`C:/Users/cg/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`；3.12.14，`-B`禁止生成工程缓存。从Popper根目录执行；新验收输出必须使用未存在的新版本路径，禁止覆盖历史结果。

```powershell
& 'C:/Users/cg/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B 'research/topics/etf_rotation_macd/tests/run_phase1_repairs_l0_v1.py' --output 'research/topics/etf_rotation_macd/decisions/PHASE1_THREE_REPAIRS_L0_v1.0_replay1.json'
& 'C:/Users/cg/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B 'research/topics/etf_rotation_macd/tests/run_etf_base_001_l0.py'
& 'C:/Users/cg/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B 'research/topics/etf_rotation_macd/tests/test_etf_price_contract_v1.py'
& 'C:/Users/cg/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B 'research/topics/etf_rotation_macd/scripts/validate_phase1_repairs_v1.py'
```
