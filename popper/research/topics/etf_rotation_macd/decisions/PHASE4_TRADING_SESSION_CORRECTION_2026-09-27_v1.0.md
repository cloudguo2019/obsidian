# 阶段4尾盘交易时段事实更正（2026-09-27）

[已观察事实｜A] 用户指出“14:57—15:00 的交易由连续竞价改为收盘集合竞价，不是从2026.7.6开始的”。复核证实：将 **2026-07-06** 说成所有 ETF 或两市收盘集合竞价的起点是错误的。[深交所 2006 年交易规则](https://www.szse.cn/disclosure/notice/t20060515_499577.html)把基金列为证券品种，并规定证券 14:57—15:00 收盘集合竞价，规则自 2006-07-01 生效；本项目 2020—2025 深市 ETF 历史段按一般竞价规则已是收盘集合竞价。[港交所 2022 年 ETF 北向交易 FAQ](https://www.hkex.com.hk/-/media/HKEX-Market/Mutual-Market/Stock-Connect/Reference-Materials/Inclusion-of-ETFs-in-Stock-Connect/Inclusion_of_ETFs_in_Stock_Connect_FAQ_Cn.pdf)也记载当时深市 ETF 有、沪市 ETF 无收盘集合竞价。

[已观察事实｜A] **2026-07-06 仅是沪市基金尾盘由连续竞价改为收盘集合竞价的生效日**。[上交所 2026 年交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)及[交易技术实施说明](https://www.sse.com.cn/services/tradingtech/development/c/10816505/files/8006a51174524e7cae832568b5e726a6.pdf)明确这一变更。故 2020—2025 年历史样本中的沪市与深市 ETF 不可共用单一尾盘撮合模型；按交易所/有效日期分段的阶段3修订门禁继续成立，但其理由应准确表述为**两市历史规则不同**。

[方法选择] [阶段4契约审阅稿 v0.2](../datasets/ETF-PHASE4_DATA_CONTRACT_REVIEW_v0.2.md)取代 v0.1 作为当前审阅入口，SHA-256 `C219543EDE8BEFB79F3119F3932B82D05169279A9772EF124A70B3D1C810DC79`。v0.1 及[原审阅记录](PHASE4_REVIEW_2026-09-25_v0.1.md)保留其 2026-09-25 身份，不追改哈希。此项仅更正交易所/日期事实与来源，不代表数据契约或预注册修订已获用户签署；当前证据 L0，正式回测/锁定开启/仿真/实盘授权仍均 0。
