---
title: ThinkTrader 股票数据接口文档
source: https://dict.thinktrader.net/dictionary/stock.html
created: 2026-05-03
tags:
  - literature
  - thinktrader
  - xtquant
  - 量化交易
aliases:
  - xtquant 股票数据接口
  - ThinkTrader 股票字典
---

# ThinkTrader 股票数据接口文档

这篇文档系统整理 ThinkTrader / xtquant 中与股票相关的数据接口，覆盖 [[合约基础信息]]、[[板块成分股]]、[[ST历史数据]]、[[行情数据]]、[[资金流向数据]]、[[订单流数据]]、[[交易日历]]、[[龙虎榜数据]]、[[北向南向资金]]、[[交易所公告数据]] 与 [[财务数据]]。

原始提取见：[[ThinkTrader 股票数据接口文档 - 原始提取]]

## 核心脉络

1. [[股票概况]]：通过 `get_instrument_detail` 获取股票或合约的基础属性，包括上市日期、退市日期、涨跌停价、流通股本、总股本、交易状态等。
2. [[行情数据]]：通过 `get_market_data_ex`、`get_market_data`、`get_full_tick` 等接口获取历史行情、实时行情、tick 数据与不同周期 K 线。
3. [[本地历史数据下载]]：历史行情、ST 历史、订单流、财务数据等接口通常依赖预先下载到本地的数据。
4. [[实时行情订阅]]：若要获取最新行情，通常需要通过 `subscribe_quote` 或相关订阅参数先建立订阅。
5. [[财务数据]]：包括 [[资产负债表]]、[[利润表]]、[[现金流表]]、[[股本表]]、[[主要指标]]、[[十大股东]]、[[股东数]] 等结构化数据。
6. [[资金流向数据]] 与 [[订单流数据]]：用于更细粒度观察成交、委托和资金行为。
7. [[北向南向资金]]、[[龙虎榜数据]]、[[交易所公告数据]]：偏事件、资金和市场公开信息维度的数据源。

## 核心概念

- [[ThinkTrader]]
- [[xtquant]]
- [[xtdata]]
- [[ContextInfo]]
- [[合约基础信息]]
- [[股票概况]]
- [[板块成分股]]
- [[ST历史数据]]
- [[行情数据]]
- [[历史行情]]
- [[实时行情订阅]]
- [[Tick数据]]
- [[涨跌停价格]]
- [[集合竞价表现]]
- [[资金流向数据]]
- [[订单流数据]]
- [[问董秘数据]]
- [[交易日历]]
- [[龙虎榜数据]]
- [[北向南向资金]]
- [[交易所公告数据]]
- [[财务数据]]

## 接口地图

| 主题 | 代表接口 / 数据 | 备注 |
| --- | --- | --- |
| [[合约基础信息]] | `get_instrument_detail` | 查询代码、名称、上市退市日期、涨跌停价、股本、交易状态等 |
| [[板块成分股]] | `get_stock_list_in_sector` | 按板块名称返回股票代码列表 |
| [[ST历史数据]] | `get_his_st_data` | 需要下载历史 ST 数据，部分权限受限 |
| [[行情数据]] | `get_market_data_ex`、`get_market_data`、`get_full_tick` | 覆盖历史行情、实时行情、tick、K 线 |
| [[资金流向数据]] | 资金流向相关接口 | 可按日级、分钟级或多标的查询 |
| [[订单流数据]] | orderflow 相关接口 | 主要以 1m 订单流为基础合成其他周期 |
| [[交易日历]] | 交易日历下载与查询 | 用于判断市场交易日 |
| [[龙虎榜数据]] | 龙虎榜相关接口 | 市场异动和席位数据 |
| [[北向南向资金]] | 沪深港通、港股通相关接口 | 包括交易日历、周期数据、持股数据 |
| [[财务数据]] | `get_financial_data`、`get_raw_financial_data` | 包括三大报表、股本、主要指标、股东数据 |

## 使用注意

- 内置 Python 接口通常以 `ContextInfo` 或策略上下文 `C` 为入口。
- 原生 Python 接口通常通过 `from xtquant import xtdata` 调用。
- 很多历史数据接口需要先执行下载函数，否则只能读到本地已有数据或返回空。
- 实时数据通常依赖订阅；没有订阅时可能无法获得最新行情。
- 部分数据属于 VIP 权限或迅投研专属数据。
- 字段命名在新旧客户端中可能存在差异，例如 `FloatVolume` 与 `FloatVolumn`。

## 建议拆分为原子笔记

- [[xtdata.get_instrument_detail 获取合约基础信息]]
- [[xtdata.get_stock_list_in_sector 获取板块成分股]]
- [[xtdata.get_his_st_data 获取 ST 历史]]
- [[xtdata.get_market_data_ex 获取历史与实时行情]]
- [[xtquant 历史行情需要先下载本地数据]]
- [[xtquant 实时行情需要先订阅]]
- [[xtquant Tick 数据字段说明]]
- [[xtquant 股票涨跌停价格数据]]
- [[xtquant 资金流向数据]]
- [[xtquant 订单流数据]]
- [[xtquant 交易日历数据]]
- [[xtquant 龙虎榜数据]]
- [[xtquant 北向南向资金数据]]
- [[xtquant 交易所公告数据]]
- [[xtdata.get_financial_data 获取财务数据]]
- [[xtquant 财务数据表字段字典]]
