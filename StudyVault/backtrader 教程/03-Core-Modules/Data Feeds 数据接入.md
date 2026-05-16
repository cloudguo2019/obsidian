---
module: data-feed
path: backtrader/feed.py
keywords: data-feed, csv, pandas, ohlc, timeframe
tags:
  - module-data-feed
  - module-backtrader
---

# Data Feeds 数据接入

## Purpose

Data Feed 把外部行情数据统一转换成 backtrader 的 OHLCV lines。策略并不直接关心 CSV、Pandas 还是在线数据源，只关心 `self.data.open/high/low/close/volume` 等标准线。

## Key Files

| File | Role |
|---|---|
| `backtrader/feed.py` | `AbstractDataBase`、数据状态、时间范围、过滤器 |
| `backtrader/feeds/csvgeneric.py` | 可配置列映射的 CSV 数据 |
| `backtrader/feeds/pandafeed.py` | Pandas DataFrame 数据 |
| `backtrader/resamplerfilter.py` | resample/replay 相关处理 |

## Public Interface

| API | Type | Description |
|---|---|---|
| `bt.feeds.GenericCSVData` | class | 通用 CSV |
| `bt.feeds.PandasData` | class | DataFrame 输入 |
| `bt.feeds.YahooFinanceCSVData` | class | Yahoo 格式 CSV |
| `fromdate`, `todate` | params | 限制数据时间范围 |
| `timeframe`, `compression` | params | 周期和压缩倍数 |
| `sessionstart`, `sessionend` | params | 交易时段 |
| `filters` | params | 对 bar 做过滤/改造 |

## GenericCSVData 示例

```python
data = bt.feeds.GenericCSVData(
    dataname="data.csv",
    dtformat="%Y-%m-%d",
    datetime=0,
    open=1,
    high=2,
    low=3,
    close=4,
    volume=5,
    openinterest=-1,
)
cerebro.adddata(data)
```

字段索引用数字指定，`-1` 表示不存在。

## PandasData 示例

```python
data = bt.feeds.PandasData(
    dataname=df,
    datetime=None,  # datetime 在 index 中
    open="open",
    high="high",
    low="low",
    close="close",
    volume="volume",
    openinterest=None,
)
```

`PandasData` 可以自动识别列名，但实盘研究中建议显式声明，减少列名大小写或命名差异造成的问题。

## Data 状态

`AbstractDataBase` 里定义了连接/实时状态，例如 `CONNECTED`, `DISCONNECTED`, `LIVE`, `DELAYED`。这些对 live data 更重要，离线回测通常主要关心是否能完整加载数据。

## Internal Flow

```text
CSV / Pandas / Online source
  |
  v
Data Feed parser
  |
  +--> datetime line
  +--> open/high/low/close/volume/openinterest lines
  |
  v
Cerebro.adddata
  |
  v
Strategy self.data
```

## Dependencies

| Direction | Module / Service | Via |
|---|---|---|
| Uses | Python datetime | 日期解析、时区转换 |
| Uses | TimeFrame | 周期定义 |
| Used by | Cerebro | `adddata`, `resampledata`, `replaydata` |
| Used by | Strategy/Indicator | `self.data.*` |

## Testing

- 先打印 `self.data.datetime.date(0)` 和 OHLC，确认列映射正确。
- 如果数据日期顺序反了，检查 feed 参数或数据文件本身。
- 对日线以上周期，注意 session end 可能影响 datetime 的内部转换。

## Related Notes

- [[Lines 数据线模型]]
- [[backtrader 快速开始]]
- [[backtrader 回测执行流]]
- [[Cerebro 运行引擎]]

