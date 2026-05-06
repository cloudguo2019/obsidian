---
title: StudyVault - XtData API 速学
tags:
  - study/xtdata
  - api/market-data
  - note/overview
aliases:
  - XtData 速学
source_url: https://dict.thinktrader.net/nativeApi/xtdata.html
---

# XtData API 速学地图

> [!info]
> 这份笔记基于 `XtQuant.XtData` 官方网页文档整理，目标是快速建立「能用」的接口认知和调用顺序。

## 学习目标

1. 搞清 `subscribe_` / `get_` / `download_` 三类接口职责。
2. 能按场景选对周期 `period` 与时间范围参数。
3. 能独立串起常见数据链路：补历史 -> 订阅实时 -> 主动查询。

## 文档结构（你需要重点看的）

- 接口概述：运行逻辑、接口分类、常用类型说明、请求限制
- 行情接口：订阅、反订阅、获取行情、下载历史、获取最新 k 线
- 财务接口：获取财务、下载财务
- 基础信息接口：合约、交易日、板块、成分股
- 附录：行情字段、数据字典、财务字段、合约字段

## 核心心智模型

```text
MiniQMT 数据源
    |
    +-- download_*   (补齐本地历史数据)
    +-- subscribe_*  (订阅实时推送)
    +-- get_*        (主动查询当前/历史数据)
```

> [!important]
> 使用 `get_*` 之前，先确认 MiniQMT 本地是否已有对应数据；缺失时先用 `download_*` 补齐。

## 三类接口速记

| 前缀 | 作用 | 典型接口 |
|---|---|---|
| `subscribe_` | 订阅实时推送 | `subscribe_quote`、全推订阅 |
| `get_` | 主动查询数据 | `get_market_data_ex`、`get_trading_calendar` |
| `download_` | 下载/补齐历史数据 | `download_history_data`、`download_financial_data` |

## 关键参数理解

### `stock_code`

- 格式：`code.market`
- 例子：`000001.SZ`、`600000.SH`、`000300.SH`

### `period`

- 常见：`tick`、`1m`、`5m`、`15m`、`30m`、`1h`、`1d`
- 扩展周期（文档版本更新中新增）：`1w`、`1mon`、`1q`、`1hy`、`1y`

### 时间范围与数量

- 区间语义：`[start_time, end_time]`
- `count = -1` 常表示尽可能返回全量
- 实战建议：避免一次性请求过大时间窗，分段拉取更稳

## 常见实战流程

### 场景 1：做日线回测

1. `download_history_data` 补齐目标标的 + 周期历史
2. `get_market_data_ex` 批量取回区间数据
3. 按复权因子（如需要）对齐价格序列

### 场景 2：做盘中监控

1. `subscribe_*` 订阅实时行情
2. 回调中做计算/打标/告警
3. 必要时用 `get_*` 补查上下文数据

### 场景 3：做选股基础池

1. `get_sector_list` / `get_stock_list_in_sector` 获取板块与成分
2. `get_instrument_detail` 拉基础信息
3. `get_trading_dates` / `get_trading_calendar` 对齐交易日

## 容易踩坑

> [!warning]
> `level2` 数据通常是实时向，不等同于可长期回补的历史库；跨交易日后要特别检查可用性与清理规则。

> [!warning]
> 文档有持续版本演进，接口名/参数可能变化（例如交易时间相关接口改名）；写代码前先核对当前版本说明。

> [!tip]
> 为不同数据域封装统一函数（行情、财务、基础信息），后续更换接口或参数时更好维护。

## 你下一步该怎么学

1. 先通读“接口概述 + 行情接口 + 附录字段列表”。
2. 挑 3 支股票，完成一次“下载 + 获取 + 订阅”的全链路脚本。
3. 做完后用这份题单自测：[[StudyVault - XtData API 自测题]]

## 参考链接

- [ThinkTrader XtData Native API](https://dict.thinktrader.net/nativeApi/xtdata.html)
- 原始提取稿：[[xtdata_native_api_raw]]
