<div style="break-inside: avoid-page; page-break-inside: avoid;">

```mermaid
graph LR
    subgraph entry["入口与配置层"]
        wrappers["run 目录场景入口"]
        unified["run_unified 主入口"]
        config["UnifiedStrategyConfig"]
        wrappers --> unified
        config --> unified
    end

    subgraph data["数据与状态层"]
        kline[("Canonical K线")]
        target[("标的池与目标仓位")]
        quote["XTData 实时行情"]
        account["QMT 资金与持仓"]
        shadow[("模拟影子账户")]
    end

    subgraph strategy["环境无关策略层"]
        loader["load_strategy_core 动态加载"]
        core["策略核心 generate_signal"]
        signal["标准 Signal 意图"]
        loader --> core --> signal
    end

    subgraph portfolio["组合决策与风控层"]
        mapping["目标仓位映射"]
        scaling["组合权重缩放"]
        sequencing["先卖后买与预算控制"]
        risk["RiskManager 校验与调整"]
        mapping --> scaling --> sequencing --> risk
    end

    subgraph runtime["运行环境适配层"]
        bt["BacktraderAdapter"]
        realtime["MiniQMTAdapter"]
        modules["执行时段管线"]
        policies["下单策略注册表"]
        btbroker["Backtrader Broker"]
        qmtgateway["MiniQMT 下单与回调网关"]
        bt --> btbroker
        realtime --> modules --> policies --> qmtgateway
    end

    subgraph output["结果与审计层"]
        logs[("信号 订单 上下文 事件日志")]
        reports["复盘与报告"]
        nextcycle["下一轮资金持仓状态"]
        logs --> reports
    end

    unified -->|按 env 分流| bt
    unified -->|按 env 分流| realtime
    unified --> loader

    kline --> bt
    kline --> core
    target --> mapping
    quote --> realtime
    account --> realtime
    shadow --> realtime

    signal --> mapping
    risk -->|回测目标订单| bt
    risk -->|实时可执行信号| modules

    btbroker --> nextcycle
    qmtgateway --> nextcycle
    nextcycle -.->|重建 StrategyContext| core

    core -.-> logs
    risk -.-> logs
    btbroker -.-> logs
    qmtgateway -.-> logs

    style wrappers,unified,config fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
    style kline,target,quote,account,shadow fill:#fff4e6,stroke:#e67700,stroke-width:2px
    style loader,core,signal fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style mapping,scaling,sequencing,risk fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style bt,realtime,modules,policies,btbroker,qmtgateway fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style logs,reports,nextcycle fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
```

</div>

# Sartre 交易逻辑拓扑图

## 总体拓扑

读图要点：策略核心只产生交易意图，不直接调用 Backtrader 或 MiniQMT。`Signal` 之后还要经过目标仓位映射、组合缩放、交易顺序控制和风控，才进入环境相关的订单执行。

## 回测、模拟和实盘的真实分叉

<div style="break-inside: avoid-page; page-break-inside: avoid;">

```mermaid
graph TB
    start["统一配置与策略核心"]
    env{"execution.env 是什么"}

    subgraph backtest["Backtest"]
        btdata["Canonical K线进入 Backtrader"]
        btcycle["每根 Bar 生成 Context 与 Signal"]
        btrisk["共享 RiskManager"]
        btorder["order_target_size 或 percent"]
        btresult["撮合结果 分析器 报告"]
        btdata --> btcycle --> btrisk --> btorder --> btresult
    end

    subgraph simulate["Simulate"]
        simquote["XTData 真实行情"]
        simcontext["QMT 启动快照"]
        simaccount["ShadowAccount 本地成交"]
        simresult["模拟订单与持仓日志"]
        simquote --> simcontext --> simaccount --> simresult
    end

    subgraph live["Live"]
        livequote["XTData 真实行情"]
        livecontext["QMT 真实资金持仓"]
        liveorder["MiniQMT 委托 撤单 查询 回调"]
        liveresult["真实订单与成交日志"]
        livequote --> livecontext --> liveorder --> liveresult
    end

    start --> env
    env -->|backtest| btdata
    env -->|simulate| simquote
    env -->|live| livequote

    style start,env fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
    style btdata,btcycle,btrisk,btorder,btresult fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style simquote,simcontext,simaccount,simresult fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style livequote,livecontext,liveorder,liveresult fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
```

</div>

三种环境共用的是配置模型、策略核心、`Signal`、`StrategyContext`、`MarketSnapshot`、风控规则和日志语义。撮合与账户状态并不共用：回测交给 Backtrader，模拟交给 `ShadowAccount`，实盘交给 MiniQMT。

## 实时主循环与日内时间窗

<div style="break-inside: avoid-page; page-break-inside: avoid;">

```mermaid
graph TB
    process["run_unified 常驻进程"]
    realtime{"处于实时总窗口"}
    idle["计算下一唤醒时间并休眠"]
    init["初始化 QMT 并订阅行情"]
    tick["可选 TickRecorder 独立线程"]
    cycle["MiniQMTAdapter.run_once 每秒调度"]

    continuous["连续竞价管线"]
    closing["收盘集合竞价管线"]
    afterhours["盘后固定价管线 可选"]
    none["当前时刻无活动执行模块"]

    etfrefresh["ETF 目标仓位盘后刷新"]
    cleanup["停止采样 取消订阅 停止 Trader"]

    process --> realtime
    realtime -->|否| etfrefresh
    etfrefresh --> idle
    realtime -->|是| init
    init --> tick
    init --> cycle

    cycle -->|09:31 至 11:30| continuous
    cycle -->|13:00 至 15:00| continuous
    cycle -->|约 14:55 至 14:57:20| closing
    cycle -->|15:05 至 15:30| afterhours
    cycle -->|没有命中时间窗| none

    continuous --> cycle
    closing --> cycle
    afterhours --> cycle
    none --> cycle
    tick -.->|共享实时行情网关| cycle
    tick -.->|健康状态门禁| afterhours
    cycle -->|到达 15:30 或退出| cleanup
    cleanup --> idle
    idle --> process

    style process,realtime,idle,init,cycle fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
    style tick,etfrefresh fill:#fff4e6,stroke:#e67700,stroke-width:2px
    style continuous fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style closing fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style afterhours fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style none,cleanup fill:#f8f9fa,stroke:#868e96,stroke-width:2px
```

</div>

边界说明：

- 实时总窗口是上午 `09:30–11:30`、下午 `13:00–15:30`。
- 连续竞价策略仍受 `is_strategy_time` 限制，最晚到 `15:00`，不会因为外层进程运行到 `15:30` 而继续下单。
- 收盘集合竞价的具体观察、确认和报单时间来自策略参数；当前高股息债配置为 `14:55:00` 开始预确认、`14:57:05–14:57:20` 报单。
- 盘后固定价模块已有实现，但当前正式 JSON 配置没有启用 `execution_modules`，所以它不是默认活动链路。
- ETF 目标仓位刷新在当前 `run_unified.py` 中固定为交易日 `16:00` 之后每天一次。
- Tick 采集线程记录行情快照，不等于策略的多周期 K 线计算器。

## 单次连续竞价决策链

<div style="break-inside: avoid-page; page-break-inside: avoid;">

```mermaid
graph LR
    bars["读取配置周期的 K线"]
    context["查询资金 持仓 行情快照"]
    core["策略核心生成 Signal"]
    targets["覆盖目标仓位映射"]
    scale["组合缩放与先卖后买"]
    price["生成受保护的执行价格"]
    risk{"RiskManager 是否通过"}
    reject["记录信号与拒绝原因"]
    execute["执行目标持仓差额"]
    policy["单次提交或两次提交"]
    gateway["模拟成交或 MiniQMT 委托"]
    callback["订单状态 查询 撤单 回调"]
    audit["记录订单 上下文 持仓"]

    bars --> core
    context --> core
    core --> targets --> scale --> price --> risk
    risk -->|否| reject
    risk -->|是| execute --> policy --> gateway --> callback --> audit
    reject --> audit
    callback -.->|更新后的账户状态| context

    style bars,context fill:#fff4e6,stroke:#e67700,stroke-width:2px
    style core,targets,scale,price fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style risk,reject fill:#ffe3e3,stroke:#c92a2a,stroke-width:2px
    style execute,policy,gateway,callback fill:#ffe8cc,stroke:#d9480f,stroke-width:2px
    style audit fill:#c5f6fa,stroke:#0c8599,stroke-width:2px
```

</div>

这里的“执行”是把目标持仓转换为当前持仓的差额，而不是简单把 `BUY` 或 `SELL` 原样发给券商。风控还会处理整手、仓位上限、现金上限、T+1、日内开平次数、涨跌停和价格笼子。

## 模块扩展边界

<div style="break-inside: avoid-page; page-break-inside: avoid;">

```mermaid
graph TB
    need{"要扩展什么能力"}

    newstrategy["新增策略核心"]
    newdata["新增数据源或周期转换"]
    newpipeline["新增交易时段或交易机制"]
    newpolicy["新增报单重试与撤单方式"]
    newrisk["新增账户级或订单级约束"]
    newreport["新增日志字段或复盘输出"]

    strategyfile["strategies 下新增 CoreStrategy"]
    datalayer["data 下扩展规范化与存储"]
    pipelinecontract["注册 ExecutionModuleSpec 与 ExecutionModule"]
    request["构造 ExecutionRequest"]
    policyregistry["向 OrderPolicyRegistry 注册策略"]
    riskmanager["扩展 RiskManager 或前置检查"]
    logger["扩展 RuntimeLogger 与 reports"]

    need -->|交易判断| newstrategy --> strategyfile
    need -->|行情输入| newdata --> datalayer
    need -->|新的时间窗| newpipeline --> pipelinecontract --> request
    need -->|新的下单编排| newpolicy --> policyregistry
    need -->|新的风险限制| newrisk --> riskmanager
    need -->|新的审计结果| newreport --> logger

    scaffold["ExecutionModuleRegistry 与 ExecutionRouter"]
    current["run_once 统一调用 Router"]
    scaffold -->|已接管实时主循环| current
    request --> current

    style need fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
    style newstrategy,newdata,newpipeline,newpolicy,newrisk,newreport fill:#e5dbff,stroke:#5f3dc4,stroke-width:2px
    style strategyfile,datalayer,pipelinecontract,request,policyregistry,riskmanager,logger fill:#d3f9d8,stroke:#2f9e44,stroke-width:2px
    style scaffold,current fill:#fff4e6,stroke:#e67700,stroke-width:2px
```

</div>

当前执行主链已经由 `ExecutionModuleRegistry` 和 `ExecutionRouter` 接管：`MiniQMTAdapter.run_once()` 只负责刷新运行状态并调用 Router，不再按模块名显式分派。新增第四种执行时段时，需要：

- 注册 `ExecutionModuleSpec`，声明默认窗口、允许窗口和可用 `OrderPolicy`。
- 实现并向 Adapter 注入 `ExecutionModule`；注册后会自动进入真实交易主循环。
- 新管线的状态机、`ExecutionRequest` 构造和审计日志。
- 必要时新增 `OrderPolicy`；如果只是复用单次或两次提交，可直接使用现有策略。
- 明确定义回测语义；Backtrader 会拒绝没有显式映射的自定义或盘后执行阶段。

内置三个管线继续保留各自的行情准备和状态机，但可执行订单统一构造成 `ExecutionRequest`，由 Router 完成幂等检查并交给 `OrderPolicyRegistry`。`Signal.execution_pipeline` 同时保留内置枚举兼容性和注册扩展所需的字符串名称。

## 对原手稿的修正

| 手稿中的表达 | 按当前工程应改为 | 原因 |
|---|---|---|
| `scheduler` 是一个独立业务模块 | `run_unified` 常驻循环加日历时间门禁 | 工程没有 APScheduler 或通用任务调度器；主循环按秒调用 `run_once()` |
| 数据层固定生成 `60m 15m 5m 1m` | 每次运行由配置选择一个 K 线周期，Tick 采集是独立旁路 | 当前没有统一的多周期聚合器，也不会自动把四个周期同时送入策略 |
| `data → signal` | `数据 + StrategyContext → CoreStrategy → Signal` | 信号依赖行情、资金、持仓和策略状态，不只依赖 DataFrame |
| `management engine` 是一个黑盒 | 拆成目标映射、组合缩放、交易顺序、风控、执行管线和订单策略 | 这些层的职责和扩展方式不同 |
| Backtrader、Live、Sim 是同一个执行器 | 三者共享策略与风控语义，但使用不同 Adapter 和账户撮合后端 | 回测由 Backtrader 撮合，Sim 用影子账户，Live 用 QMT 真实账户 |
| 执行系统之后直接进入分析 | 订单状态先通过查询、撤单、回调和账户状态闭环，再进入日志与报告 | 报单成功不等于成交完成 |
| 运行结果直接反馈给策略对象 | 下一轮重新查询或读取账户，重建 `StrategyContext` | 当前主要反馈载体是账户与持仓状态，不是统一的策略事件总线 |
| 逆回购属于统一主循环的一个普通节点 | 逆回购有独立入口和 `15:15–15:30` 轮询循环 | `run_miniqmt_reverse_repo.py` 不由 `run_unified.run_once()` 调度 |
| 日志只在末端产生 | 信号、上下文、订单、Tick、执行模块和错误各阶段都写审计日志 | RuntimeLogger 是横切能力 |

## 已修正的实现与文案不一致

`run_etf_rotation_live.py` 的提示文字已从“`22:00` 刷新”改为 `16:00`，与 `ETF_ROTATION_TARGET_REFRESH_TIME` 保持一致。

模块注册表、配置规格和 Router 现在共同构成实时执行主链；内置管线中的策略准备逻辑仍是 Adapter 侧回调，不应误读为所有业务状态机都已经移入 engine 包。

## 代码依据

| 关注点 | 主要代码 |
|---|---|
| 统一入口与环境分流 | [`run/run_unified.py`](../run/run_unified.py) |
| 实时时间边界 | [`sartre_core/data/calendar.py`](../sartre_core/data/calendar.py) |
| 配置模型 | [`sartre_core/config/runtime_config.py`](../sartre_core/config/runtime_config.py) |
| 策略动态加载 | [`sartre_core/strategies/__init__.py`](../sartre_core/strategies/__init__.py) |
| 标准信号与上下文 | [`sartre_core/engine/signal.py`](../sartre_core/engine/signal.py)、[`context.py`](../sartre_core/engine/context.py) |
| 风控 | [`sartre_risk/risk_manager.py`](../sartre_risk/risk_manager.py) |
| 回测执行 | [`sartre_core/adapters/backtrader_adapter.py`](../sartre_core/adapters/backtrader_adapter.py) |
| 模拟与实盘执行 | [`sartre_core/adapters/miniqmt_adapter.py`](../sartre_core/adapters/miniqmt_adapter.py) |
| 执行模块契约 | [`sartre_core/engine/execution_modules.py`](../sartre_core/engine/execution_modules.py) |
| 订单策略 | [`sartre_core/engine/order_policies.py`](../sartre_core/engine/order_policies.py) |
| Tick 采集与共享行情网关 | [`sartre_core/data/market_tick.py`](../sartre_core/data/market_tick.py) |
| 逆回购独立循环 | [`run/run_miniqmt_reverse_repo.py`](../run/run_miniqmt_reverse_repo.py) |
| 日志与报告 | [`sartre_core/engine/runtime_logger.py`](../sartre_core/engine/runtime_logger.py)、[`sartre_core/reports`](../sartre_core/reports) |
