---
title: "Xt完整实例练习题"
created: 2026-05-08
source_pdf: "code_examples_raw.md"
part: "practice"
keywords:
  - practice
  - xtquant
  - market-data
  - trading-api
tags:
  - quant-trading
  - xtquant
  - practice
---

# Xt完整实例练习题

#practice #xtquant #xtdata #xttrader

## Related Concepts

- [[Xt行情完整实例]]
- [[Xt交易完整实例]]
- [[接口速查]]
- [[易错点]]

> [!hint]- 答题关键词
> | Keyword | Answer |
> | --- | --- |
> | 补历史 | `download_history_data` 后再查询 |
> | 实时行情 | `subscribe_quote` + 查询或 callback |
> | 主线程保活 | 行情用 `xtdata.run()`，交易用 `run_forever()` |
> | 异步下单 | 响应、委托、成交是不同事件 |
> | 重连 | 有限 session 范围，失败后报警 |

---

## Question 1 - 历史行情为空 [recall]

> 你直接调用 `get_market_data_ex` 读取 1 分钟 K 线，结果为空。完整实例提示你应该先做什么？

> [!answer]- 答案
> 先确认 MiniQmt 本地是否已有数据；不足时调用 `download_history_data(code, period='1m', ...)` 补充，再用查询接口读取。

---

## Question 2 - 下载接口返回值 [recall]

> `download_history_data` 被调用后没有返回行情 DataFrame，这是不是异常？

> [!answer]- 答案
> 不是。下载接口负责把数据补到本地，后续需要用 `get_market_data` 或 `get_market_data_ex` 读取。

---

## Question 3 - 订阅后仍拿不到实时数据 [application]

> 你设置了 `subscribe_quote(code, callback=f)`，但脚本运行完马上退出，回调没有持续触发。该怎么改？

> [!answer]- 答案
> 在行情脚本末尾使用 `xtdata.run()` 阻塞主线程，确保订阅回调有机会持续执行。

---

## Question 4 - 轮询和回调选择 [analysis]

> 一个低频策略每 3 秒刷新一次行情，另一个策略需要 tick 更新时立刻处理。两者分别更适合什么模式？

> [!answer]- 答案
> 低频策略适合固定间隔轮询 `get_market_data_ex`；tick 触发策略适合 `subscribe_quote(..., callback=f)`，但 callback 应保持轻量。

---

## Question 5 - VIP 行情连接顺序 [recall]

> 连接 VIP 行情服务器时，`xtdc.listen` 和 `xtdata.connect` 的关系是什么？

> [!answer]- 答案
> `xtdc.listen` 先启动本地监听并返回端口，`xtdata.connect(port=port)` 再让 Python 行情层连接该端口。

---

## Question 6 - 对手价兜底 [application]

> 卖出时你想用买一价作为对手价，但 `bidPrice[0]` 为 0。完整实例怎么处理？

> [!answer]- 答案
> 示例用最新价 `lastPrice` 兜底：`bidPrice[0] != 0` 时取买一，否则取最新价。实盘还应检查涨跌停和品种规则。

---

## Question 7 - 交易初始化顺序 [recall]

> 写出交易示例里从创建交易对象到订阅账户的核心顺序。

> [!answer]- 答案
> 创建 `XtQuantTrader(path, session_id)`，注册 callback，`start()`，`connect()`，再 `subscribe(account)`。

---

## Question 8 - 异步响应和成交 [analysis]

> 为什么不能把 `on_order_stock_async_response` 当成成交确认？

> [!answer]- 答案
> 它只表示异步下单请求收到响应。委托状态要看 `on_stock_order`，真正成交要看 `on_stock_trade`。

---

## Question 9 - 买入数量计算 [application]

> 可用资金 18,000 元，目标买入金额 20,000 元，当前价 12 元。按示例的 100 股取整规则，买入数量是多少？

> [!answer]- 答案
> 先取 `min(20000, 18000)=18000`，`int(18000 / 12 / 100) * 100 = 1500` 股。

---

## Question 10 - 防止重复下单 [analysis]

> 定时判断实盘示例为什么要记录 `(K线时间, 买卖方向)` 这样的 `order_record`？

> [!answer]- 答案
> 防止同一根 K 线内同一方向信号重复触发，导致多次下单。

---

## Question 11 - 重连 session 范围 [application]

> 交易断开后，为什么不建议用无限循环不断创建新的 `session_id` 重连？

> [!answer]- 答案
> 每次连接都会创建对接文件，无限制创建可能占满硬盘并导致系统异常。应使用有限 session 范围，耗尽后报警或人工处理。

---

## Question 12 - 回调撤单链路 [analysis]

> 你想在委托报入后按柜台合同编号撤单，应在哪个回调里更容易拿到 `order_sysid`？

> [!answer]- 答案
> 通常在 `on_stock_order` 委托回报中读取 `order.order_sysid`，确认状态和合同编号有效后调用 `cancel_order_stock_sysid_async`。

---

> [!summary]- 复盘表
> | 易错点 | 正确动作 |
> | --- | --- |
> | 查历史前没补数 | 先下载，再查询 |
> | callback 不触发 | 确认订阅、确认新增 tick、阻塞主线程 |
> | 异步响应当成交 | 分清响应、委托、成交 |
> | 无限重连 | 有限 session 范围 |
> | 重复下单 | 记录信号时间和方向 |

