# HD-ANCHOR-001 阶段5补充：独立价格副源与2012年前税费

## 1. 本阶段要回答的研究问题

[方法选择｜C] 关闭Xtquant独立价格副源缺口，并核对机器税费表是否遗漏原始MD已记载的2012年前费用。

## 2. 理论和公式

[方法选择｜C] 逐日价格相对差异为`|Xtquant-AkShare|/|Xtquant|`；超过1%进入重大差异复核。成交量按`AkShare股数/100`转换为手。

[计算结果｜A] 2003年沪市经手费为`0.105‰+0.005‰=0.110‰`，证管费由0.045‰降至0.040‰，两项合计维持0.150‰。

## 3. 实际操作

[已观察事实｜A] 已安装Python 3.11.9和隔离虚拟环境，固定AkShare 1.18.94；通过AkShare/Sina获取不复权日线并保留只读原始快照。

[已观察事实｜A] 已生成标准化副源、Parquet、两源逐日差异表、数据报告和SHA-256清单；未修改Xtquant主数据。

[已观察事实｜A] 已生成税费机器表v2，保留v1不覆盖。

## 4. 执行结果

[计算结果｜A] Xtquant与AkShare/Sina各5,118行，共同日期5,118行，仅单一来源日期0行。

[计算结果｜A] OHLC分币容差一致5,114行，4行收盘价相差0.01元；最大相对差异0.077101%，超过1%的记录0行。

[计算结果｜A] 成交量最大差1.04手、最大相对差0.002728%；成交额最大差172元、最大相对差0.0000066%。

## 5. 需要研究者提供的数据或选择

[待办事项｜C] 若未来把2003—2012扩展期用于正式经济结论，应决定是否接受0.110‰经手费的B级连续性假设，并补取2012年前过户费精确生效档案。

[已观察事实｜A] 2018年开始的预注册主研究期不需要上述选择。

## 6. 产物路径

[已观察事实｜A] 价格核验报告为[`akshare_price_crosscheck_2026-09-10.md`](akshare_price_crosscheck_2026-09-10.md)，源清单为[`akshare_price_source_manifest_v1.json`](akshare_price_source_manifest_v1.json)，逐日差异表为[`derived/600900_xtquant_akshare_price_crosscheck_v1.csv`](derived/600900_xtquant_akshare_price_crosscheck_v1.csv)。

[已观察事实｜A] 税费v2及说明位于[`schedules/a_share_transaction_cost_schedule_v2_pre2012.csv`](schedules/a_share_transaction_cost_schedule_v2_pre2012.csv)和[`schedules/a_share_transaction_cost_schedule_v2_pre2012_note.md`](schedules/a_share_transaction_cost_schedule_v2_pre2012_note.md)。

## 7. 验收标准

[计算结果｜A] 日期一一对应、OHLC约束通过、价格均为正、重大价格差异0行，独立价格副源门禁`PASS`。

[计算结果｜A] 2012年前经手费与证管费已机器化；早期过户费未知起点没有被伪造，税费修订`PASS_WITH_DOCUMENTED_LIMITATION`。

## 8. 问题和证据等级

[已观察事实｜B] AkShare价格上游是新浪财经，不是交易所原始数据。

[已观察事实｜B] 4个收盘价差异日为2015-12-03、2017-02-28、2018-01-23和2018-06-25，均相差0.01元且低于1%差异阈值。

[已知限制｜B] 两个供应商可能共享交易所基础行情，双源一致主要排除文件损坏、日期错位和复权口径错误，不能替代交易所逐笔原始档案。

## 9. 是否允许进入下一阶段

[方法选择｜C] 阶段5数据门禁通过，允许在研究者确认后进入阶段6样本划分。正式回测、锁定集、仿真和实盘仍未授权。

