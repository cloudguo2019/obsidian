# 长江电力（600900.SH）实际现金分红公司行动表

> 数据建立：2026-09-09（Asia/Shanghai）  
> 数据截止：2026-09-09  
> 覆盖：2020 年度至 2025 年度已经实施的 8 笔 A 股现金分红（2024、2025 年度均包含中期和末期）  
> 用途：未复权账户的真实现金分红入账；不用于替换 `expected_annual_dividend_per_share`。

## 1. 使用口径

- `cash_dividend_per_share` 是**符合该笔分配资格的 A 股每股税前实际获派额**。账户按登记日收盘持仓确认应收、在除息日确认应收股息、在发放日把应收转为可用现金。
- `ex_reference_dividend_per_share` 只在差异化分红时填写，是上交所计算除息参考价的“全股本摊薄现金红利”；不能替代实际获派额。非差异化分红填空值，而不是重复填写现金红利。
- 表内日期均为上海证券交易所 A 股日期。GDR 的伦敦到账时间不替代 A 股 `pay_date`。
- `announcement_date` 为载有实施日期的权益分派实施公告的披露日，不是最初利润分配预案日；精确披露时分秒尚未归档，不能反向用于 PIT 分红预期。

## 2. 可导入事件表

机器可读副本：[600900_cash_dividend_actions_2021_2026.csv](600900_cash_dividend_actions_2021_2026.csv)。下列内容与 CSV 保持一致，便于人工审计。

```csv
action_id,symbol,action_type,distribution_period,announcement_date,record_date,ex_date,pay_date,cash_dividend_per_share,currency,ex_reference_dividend_per_share,distribution_is_differential,eligible_share_class,entitlement_rule,tax_rule_version,tax_assumption,source,secondary_source,version,record_status
600900-CASH-DIV-2020-FY-20210716,600900.SH,CASH_DIVIDEND,2020年度,2021-07-09,2021-07-15,2021-07-16,2021-07-16,0.700000,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2021-033,Sohu/中国证券报公告全文转载,v1,VALID
600900-CASH-DIV-2021-FY-20220721,600900.SH,CASH_DIVIDEND,2021年度,2022-07-13,2022-07-20,2022-07-21,2022-07-21,0.815300,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,上交所实施公告,Sohu上交所公告索引,v1,VALID
600900-CASH-DIV-2022-FY-20230721,600900.SH,CASH_DIVIDEND,2022年度,2023-07-17,2023-07-20,2023-07-21,2023-07-21,0.853300,CNY,0.821100,true,A股（有资格的23,546,295,291股）,登记日收市后登记在册；重大资产重组取得的921,922,425股不参与,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__LIMITED_NATURAL_FUND_10PCT_WHT__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2023-036,三峡EB换股价调整公告,v1,VALID
600900-CASH-DIV-2023-FY-20240719,600900.SH,CASH_DIVIDEND,2023年度,2024-07-11,2024-07-18,2024-07-19,2024-07-19,0.820000,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2024-030,巨潮资讯法定公告镜像,v1,VALID
600900-CASH-DIV-2024-INTERIM-20250124,600900.SH,CASH_DIVIDEND,2024年中期,2025-01-16,2025-01-23,2025-01-24,2025-01-24,0.210000,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2025-004,中国证券报公告页,v1,VALID
600900-CASH-DIV-2024-FY-20250718,600900.SH,CASH_DIVIDEND,2024年度末期,2025-07-11,2025-07-17,2025-07-18,2025-07-18,0.733000,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2025-032,巨潮资讯法定公告镜像,v1,VALID
600900-CASH-DIV-2025-INTERIM-20260212,600900.SH,CASH_DIVIDEND,2025年中期,2026-02-05,2026-02-11,2026-02-12,2026-02-12,0.210000,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2026-005,中国证券报公告页,v1,VALID
600900-CASH-DIV-2025-FY-20260717,600900.SH,CASH_DIVIDEND,2025年度末期,2026-07-10,2026-07-16,2026-07-17,2026-07-17,0.790000,CNY,,false,A股,登记日收市后登记在册的全体A股股东,PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85,INDIVIDUAL_DEFERRED_BY_HOLDING_PERIOD__QFII_STOCK_CONNECT_GDR_10PCT_WHT__OTHER_SELF_ASSESS,长江电力2026-027,新浪财经公告全文镜像,v1,VALID
```

## 3. 人工复核总表

| 分配期间 | 登记日 | 除息日 | 发放日 | 实际获派（元/股，含税） | 差异化除息参考额（元/股） | 差异化及资格 |
|---|---|---|---|---:|---:|---|
| 2020 年度 | 2021-07-15 | 2021-07-16 | 2021-07-16 | 0.700000 | — | 否；全体 A 股 |
| 2021 年度 | 2022-07-20 | 2022-07-21 | 2022-07-21 | 0.815300 | — | 否；全体 A 股 |
| 2022 年度 | 2023-07-20 | 2023-07-21 | 2023-07-21 | 0.853300 | 0.821100 | 是；23,546,295,291 股参与，重大资产重组取得的 921,922,425 股不参与 |
| 2023 年度 | 2024-07-18 | 2024-07-19 | 2024-07-19 | 0.820000 | — | 否；全体 A 股 |
| 2024 年中期 | 2025-01-23 | 2025-01-24 | 2025-01-24 | 0.210000 | — | 否；全体 A 股 |
| 2024 年度末期 | 2025-07-17 | 2025-07-18 | 2025-07-18 | 0.733000 | — | 否；全体 A 股 |
| 2025 年中期 | 2026-02-11 | 2026-02-12 | 2026-02-12 | 0.210000 | — | 否；全体 A 股 |
| 2025 年度末期 | 2026-07-16 | 2026-07-17 | 2026-07-17 | 0.790000 | — | 否；全体 A 股 |

2024 年度全年税前现金分红为 `0.210000 + 0.733000 = 0.943000` 元/股；2025 年度为 `0.210000 + 0.790000 = 1.000000` 元/股。两笔中期分红已经是独立的现金行动，账户中不得在年度末期再次重复入账。

### 2022 年度差异化分红的强制分离

实际获派额和除息参考额分别服务于不同用途：

```text
普通有资格股份的现金应收 = 登记日持股数 × 0.853300 元
不参与的 921,922,425 股现金应收 = 0 元

仅用于交易所除息参考价：
0.821100 ≈ (23,546,295,291 × 0.853300) ÷ 24,468,217,716
```

所以，持有普通有资格 A 股的账户不能按 0.821100 元入账，也不能对不参与的重组股份按 0.853300 元入账。

## 4. 税务版本和到账金额

### `PRC_LISTED_DIVIDEND_PIT_2015_101+2012_85`

所有 8 个登记日均晚于 2015-09-08，适用财税〔2015〕101 号所规定的上市公司股息红利差别化个人所得税版本，并按财税〔2012〕85 号处理操作细节：

| 账户类别 | 派息日入账 | 最终税负/处理 | 最终净额（以税前每股红利 `D` 表示） |
|---|---|---|---:|
| 自然人、证券投资基金无限售流通股 | 先按 `D` 派发，暂不扣税 | 登记日后卖出时由中国结算/券商按持有期追补：≤1月 20%；1月—1年 10%；>1年 0% | `0.8D` / `0.9D` / `D` |
| 自然人、基金限售股 | 公告明示时按 10% 代扣 | 适用于 2022 年度差异化分红公告所列限售股 | `0.9D` |
| QFII | 公司按 10% 代扣 | 可按税收协定另行申请待遇 | `0.9D` |
| 沪股通（香港联交所投资者） | 公司按 10% 代扣 | 可按较低协定税率申请退税 | `0.9D` |
| GDR 投资者 | 公司按 10% 扣缴 | 可按税收协定另行申请待遇；到账以托管行安排为准 | `0.9D` |
| 其他投资者/公司自行发放对象 | 公司不代扣或自行缴纳 | 以各自适用税法申报 | 派息时 `D` |

**账户实现要求：** A 股个人账户在 `pay_date` 增加 `cash_available = shares × D`，同时建立或更新潜在 `tax_liability`；不能在 `pay_date` 直接按 20% 把现金净额写成 `0.8D`，因为公告约定的扣收时点是登记日后实际转让股票时。逐批持有期需要由交易流水决定，不能只由公司行动表推断。

下表给出便于对账的最终税后等值（不等于 A 股个人在派息日立即收到的现金）。QFII、沪股通和 GDR 在没有协定优惠时等于“10% 预扣”列。

| 分配期间 | 税前 D | 个人 ≤1月（20%） | 个人 1月—1年（10%） | 个人 >1年（0%）/其他派息额 | QFII、沪股通、GDR（10% 预扣） |
|---|---:|---:|---:|---:|---:|
| 2020 年度 | 0.700000 | 0.560000 | 0.630000 | 0.700000 | 0.630000 |
| 2021 年度 | 0.815300 | 0.652240 | 0.733770 | 0.815300 | 0.733770 |
| 2022 年度 | 0.853300 | 0.682640 | 0.767970 | 0.853300 | 0.767970 |
| 2023 年度 | 0.820000 | 0.656000 | 0.738000 | 0.820000 | 0.738000 |
| 2024 年中期 | 0.210000 | 0.168000 | 0.189000 | 0.210000 | 0.189000 |
| 2024 年度末期 | 0.733000 | 0.586400 | 0.659700 | 0.733000 | 0.659700 |
| 2025 年中期 | 0.210000 | 0.168000 | 0.189000 | 0.210000 | 0.189000 |
| 2025 年度末期 | 0.790000 | 0.632000 | 0.711000 | 0.790000 | 0.711000 |

## 5. 证据与交叉核验

| 分配期间 | 法定/公司主来源 | 独立核验 | 结果 |
|---|---|---|---|
| 2020 年度 | [公司实施公告（2021-033）](https://www.cypc.com.cn/eportal/fileDir/cypcweb/cypc/accessory/20210709145608.pdf) | [中国证券报公告全文转载](https://www.sohu.com/a/476372925_120988533) | 日期、每股 0.70 元、全体 A 股一致 |
| 2021 年度 | [上交所实施公告](https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2022-07-13/600900_20220713_1_zI17tKH7.pdf) | [上交所公告索引及分红日期](https://q.stock.sohu.com/cn/600900/bw_49.shtml) | 登记日 2022-07-20、除息/发放日 2022-07-21、每股 0.8153 元一致 |
| 2022 年度 | [实施公告（2023-036）](https://static.cninfo.com.cn/finalpage/2023-07-17/1217309077.PDF) | [三峡 EB 换股价调整公告](https://static.sse.com.cn/disclosure/bond/announcement/exchangeable/c/new/2023-07-19/132018_20230719_6OER.pdf) | 0.8533 元实际额、0.8211 元参考额、2023-07-21 生效一致 |
| 2023 年度 | [实施公告（2024-030）](https://static.cninfo.com.cn/finalpage/2024-07-11/1220602045.PDF) | [公告全文镜像](https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=10129212&stockid=600900) | 日期、每股 0.82 元一致 |
| 2024 年中期 | [实施公告（2025-004）](https://stockn.xueqiu.com/SH600900/20250115986743.pdf) | [中国证券报公告页](https://epaper.cs.com.cn/zgzqb/images/2025-01/16/B009/zqB00916.pdf) | 日期、每股 0.21 元一致 |
| 2024 年度末期 | [实施公告（2025-032）](https://static.cninfo.com.cn/finalpage/2025-07-11/1224131238.PDF) | [公告全文镜像](https://4g.stockstar.com/detail/SN2025071100000433) | 日期、每股 0.733 元一致 |
| 2025 年中期 | [实施公告（2026-005）](https://epaper.cs.com.cn/zgzqb/images/2026-02/05/B025/zqB02505.pdf) | [公告摘要](https://xueqiu.com/S/SH600900/notices?page=63) | 日期、每股 0.21 元一致 |
| 2025 年度末期 | [上交所实施公告（2026-027）](https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-07-10/600900_20260710_T5C7.pdf) | [公告全文镜像](https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12437930&stockid=600900) | 日期、每股 0.79 元一致 |

个人所得税版本的官方依据为[国家税务总局：财税〔2015〕101 号](https://www.chinatax.gov.cn/chinatax/n810341/n810765/n1465977/n1466017/c1967339/content.html)：登记日在 2015-09-08 后的上市公司红利适用该版本；其规定了 >1 年暂免、≤1 月按 20%、1 月—1 年按 50%计税基础并适用 20%税率，以及“派息时暂不扣、卖出时追补”的机制。

## 6. 范围和下一步

本表完成了实际现金行动所需的日期、税前实际每股额、差异化除息参考额和税务版本；它仍不是逐笔持仓税务台账。进入账户回放时，必须把每个 `lot_id` 的买入、卖出、登记日持股和递延税负结清日与本表连接，才可确定每位投资者的最终税额。

本文件尚未把公告 PDF 下载为只读原始文件或计算其 SHA-256；因此可作为结构化候选和双源核验依据，但在 `HD-DATA-CONTRACT-1.0` 的正式阶段 5 验收前，仍需归档原文并在数据清单登记哈希、获取时间和行级 `raw_record_id`。
