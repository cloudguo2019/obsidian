---
title: "Xttrade 练习题"
created: 2026-05-07
source_pdf: "xttrader_raw.md"
part: "practice"
keywords:
  - practice
  - callback
  - order-flow
  - query
  - account-status
tags:
  - quant-trading
  - xttrader
  - practice
---

# Xttrade 练习题（10题）

## Related Concepts

- [[XtQuant运行与数据模型]]
- [[交易接口与回调实战]]

> [!hint]- 速查提示（折叠）
> | 关键词 | 结论 |
> | --- | --- |
> | `session_id` | 不同策略要区分，避免会话冲突 |
> | `subscribe` | 不订阅就没有主推 |
> | `order_stock_async` | 用 `seq` 对齐异步回报 |
> | 回调内查询 | 慎用同步查询，注意时序与阻塞 |

## Q1 - 生命周期排序 [recall]
> 请写出从策略启动到接收主推的最小步骤顺序。

> [!answer]- 参考答案
> `XtQuantTrader -> register_callback -> start -> connect -> subscribe -> run_forever`。缺少订阅时通常收不到交易主推。

## Q2 - 会话编号作用 [recall]
> `session_id` 的设计目的是什么？

> [!answer]- 参考答案
> 它是与 MiniQMT 通信的会话标识，不同策略应使用不同编号，否则可能出现会话混淆或消息错配。

## Q3 - 同步与异步下单差异 [recall]
> `order_stock` 与 `order_stock_async` 的返回值分别是什么？

> [!answer]- 参考答案
> `order_stock` 返回 `order_id`；`order_stock_async` 返回请求序号 `seq`，后续要在异步回调中关联。

## Q4 - 撤单失败排查 [application]
> 你调用了撤单接口但没有撤成功，优先检查哪三类信息？

> [!answer]- 参考答案
> 检查委托当前状态（是否可撤）、回调中的 `on_cancel_error` 错误码/错误信息、以及账户连接与订阅状态是否正常。

## Q5 - 查询返回 None [application]
> `query_stock_positions` 返回 `None`，你的处理策略是什么？

> [!answer]- 参考答案
> 先判定是查询失败还是当日无数据，再结合账户状态与日志重试；必要时用回调数据做临时状态兜底。

## Q6 - 推送中同步查询卡住 [analysis]
> 在 `on_stock_order` 里同步查全量委托，程序偶发卡顿。请分析原因与改法。

> [!answer]- 参考答案
> 原因是回调线程中阻塞查询导致时序排队。改法是改用异步查询，或启用宽松时序并接受查询与推送顺序不完全一致。

## Q7 - 订单状态机理解 [analysis]
> 为什么“部成待撤”和“部撤”要区分？

> [!answer]- 参考答案
> “部成待撤”表示撤单请求未最终完成；“部撤”表示撤单已落地，剩余未成交部分已撤。两者对应的后续风险动作不同。

## Q8 - 最小风控闭环设计 [application]
> 用哪些回调和查询可以构建一个最小风控闭环？

> [!answer]- 参考答案
> 以 `on_stock_order`、`on_stock_trade` 跟踪实时变化，`on_order_error`/`on_cancel_error` 处理异常，再用 `query_stock_positions` 和 `query_stock_asset` 做兜底校验。

## Q9 - 账户类型选择 [recall]
> 信用账户查询融资融券标的应使用哪个接口组？

> [!answer]- 参考答案
> 使用信用查询接口组，例如 `query_credit_subjects`、`query_credit_slo_code`、`query_credit_assure`。

## Q10 - 接口分层复盘 [analysis]
> 请解释为什么要把初始化、交易、查询、回调分层，而不是写成一个大函数。

> [!answer]- 参考答案
> 分层能降低耦合并提高可观测性：初始化负责连接稳定性，交易负责动作发起，回调负责事件驱动，查询负责一致性校验，便于定位问题和扩展策略。

> [!summary]- 复盘要点（折叠）
> | 主题 | 必会结论 |
> | --- | --- |
> | 会话与连接 | 先连通再交易，`session_id` 要唯一化 |
> | 交易动作 | 同步看 `order_id`，异步看 `seq` |
> | 数据一致性 | 回调是主线，查询做校验 |
> | 时序风险 | 回调内慎用阻塞查询 |

