# FINITUDE / SARTRE 从 MiniQMT 迁移到大 QMT：可实施方案

> 文档状态：实施基线 v1.0  
> 编制日期：2026-09-10  
> 目标日期：2026-09-30 前完成可控切换  
> 适用仓库：`C:\quant\MiniQMT\sartre`

## 1. 结论

本次不把策略代码整体改写成大 QMT 内置策略。目标架构是：

```text
FINITUDE / SARTRE（外部 Python 3.11）
  策略核心 → 目标持仓 → 风控 → 订单策略 → BigQMT Gateway
                                             │
                                             ▼
                                  本机 SQLite Bridge
                                             │
                                             ▼
大 QMT 内置 Python（薄执行端）
  快照 → 本地硬风控 → passorder/cancel → 回调归一化 → SQLite
                                             │
                                             ▼
                                          券商柜台
```

第一版选 **SQLite**，不选 JSONL、HTTP 或 socket。SQLite 能用唯一约束和事务解决两个进程间的抢占、重启恢复和重复消费；JSONL 保留为每日审计导出格式，不作为控制通道。

切换的 P0 范围只有当前真正需要的三条生产路径：

1. ETF 轮动的收盘集合竞价执行；
2. 高股息债策略的收盘集合竞价执行；
3. 逆回购。

连续竞价、近似盘中收盘、盘后固定价格属于 P1，P0 切换稳定后再接。当前代码实际上有四个股票执行模块，而不是初步方案所说的三个。

必须采用 **fail-closed（失败即停止）**：状态不确定时不得自动重发。`passorder()` 没有返回订单号，QMT 又是异步回报模型，因此无法实现券商侧严格的 exactly-once；可实现的是“本地幂等 + 不确定时停单 + 启动对账”，优先漏单而不是重复下单。

## 2. 对初步方案的三项修正

### 2.1 Router 已经接管 `run_once()`，不应重做一套

仓库现状：

- `sartre_core/engine/execution_modules.py` 已有 `ExecutionModuleRegistry` 和 `ExecutionRouter`；
- `sartre_core/adapters/miniqmt_adapter.py` 的 `run_once()` 已通过 Router 分派；
- `sartre_core/engine/order_policies.py` 已有单次提交和两次提交策略；
- `sartre_core/adapters/miniqmt_order_policy_gateway.py` 是当前 MiniQMT 提交端。

因此正确改造是保留 Registry、Router 和 OrderPolicy，把 MiniQMT Gateway 换成 BigQMT Gateway；同时逐步把目前仍藏在 MiniQMT mixin 中的编排状态机抽出，而不是复制一个新的 BigQMTAdapter 巨类。

### 2.2 “行情完全不迁”在当前代码中不可行

历史 K 线、Parquet、PIT、排名、指标和回测可以保持不动。但是当前实盘还直接依赖 `xtquant` 完成：

- 实时 Tick 和盘口；
- 资产、持仓、委托、成交查询；
- 订单回报；
- 16:00 后的日线刷新。

所以应明确拆成两类数据：

| 数据 | P0 处理方式 |
|---|---|
| 历史 K 线、Parquet、排名、策略计算 | 保留现有外部体系 |
| 执行前 Tick、盘口、交易状态、账户、持仓、委托、成交 | 必须由大 QMT Bridge 提供 |
| 16:00 日线更新 | Phase 0 验证外部 `xtdata` 停权后是否仍可用；不可用则改为大 QMT 导出或备用数据源 |

“MiniQMT 停用后外部 `xtdata` 仍可用”不能作为未经验证的上线前提。

### 2.3 `passorder()` 调用成功不等于订单已受理

大 QMT 官方接口中，`passorder(...)` 的返回值是 `None`。真正的订单号与状态只能从订单回调、成交回调或 `get_trade_detail_data()` 查询结果中确认。取消接口的布尔返回也只表示撤单请求已发出，不表示已经撤成。

因此禁止以下实现：

```text
调用 passorder()
→ 立即把命令写成 SUBMITTED
→ 超时就再调用一次
```

正确流程是：

```text
事务写入 SUBMITTING
→ 调用 passorder()
→ 按 remark_token 等待回调/查询匹配
→ ACKNOWLEDGED / REJECTED / UNKNOWN
```

`UNKNOWN` 必须人工处置，不能自动重发。

## 3. 本期范围与不做事项

### 3.1 P0 必须完成

- 大 QMT API 和实际券商版本探针；
- SQLite Bridge、命令和事件状态机；
- 大 QMT 薄执行策略；
- BigQMTOrderPolicyGateway；
- 账户、持仓、委托、成交、Tick 快照归一化；
- 收盘集合竞价两条策略链路；
- 逆回购链路；
- 独立硬风控、心跳、kill switch；
- 幂等、重启恢复、启动对账；
- Dry Run、影子核对、小资金实盘和切换手册。

### 3.2 P0 明确不做

- 不把策略核心搬进 QMT；
- 不在 QMT 内安装 pandas、Backtrader 或项目完整依赖；
- 不迁历史数据目录和回测数据链路；
- 不做 HTTP/socket；
- 不一次性重写全部四个执行模块；
- 不删除 MiniQMT 代码；
- 不承诺券商侧 exactly-once；
- 不让外部引擎动态提高大 QMT 的本地资金上限。

## 4. 目标代码结构

建议在现有仓库内新增或调整如下：

```text
sartre_core/
├── engine/
│   ├── execution_modules.py              # 保留 Registry/Router；去除 broker int 泄漏
│   ├── order_policies.py                 # 保留单次/两次提交策略
│   ├── broker_contracts.py               # 新增：BrokerOrderIntent/Report/类型别名
│   └── reconciliation.py                 # 新增：外部引擎对账
├── execution/
│   ├── closing_auction_coordinator.py    # 新增：从 MiniQMT mixin 抽出 P0 编排
│   └── reverse_repo_coordinator.py       # 新增：逆回购编排
├── ipc/
│   ├── schema.sql                        # 新增：Bridge 数据库结构
│   ├── sqlite_bridge.py                  # 新增：外部 Python 3.11 客户端
│   ├── state_machine.py                  # 新增：合法状态迁移
│   └── audit_export.py                   # 新增：按日导出 JSONL
├── adapters/
│   ├── bigqmt_order_policy_gateway.py    # 新增：实现现有 OrderPolicyGateway
│   ├── bigqmt_market_account.py          # 新增：读取大 QMT 快照
│   ├── miniqmt_order_policy_gateway.py   # 暂留，作为并行核对/回退
│   └── miniqmt_*.py                      # 暂留，不继续扩张
└── config/
    ├── bigqmt_config.example.json        # 新增：非敏感示例
    └── local_config.json                 # 本机敏感配置，必须 gitignore

bigqmt_runtime/                            # 独立部署单元，兼容 QMT 内置 Python
├── qmt_strategy.py                       # QMT 入口与全局回调
├── bridge_db.py                          # 仅 sqlite3，短事务
├── mapper.py                             # 23/24/1101/5/11/49 等映射
├── normalizer.py                         # m_* 原始结构 → 稳定字典
├── hard_risk.py                          # 本地独立硬风控
├── remark.py                             # 短 token 生成与校验
├── probe_strategy.py                     # Phase 0 探针
└── local_settings.example.py             # 不含账户和真实路径

run/
├── run_bigqmt_live.py                    # 新增：强制 preflight 后启动引擎
├── run_bigqmt_dry_run.py                 # 新增：生成真实意图但禁止 passorder
└── export_bigqmt_audit.py                # 新增：收盘后审计导出

tools/
└── build_bigqmt_bundle.py                 # 新增：生成带版本与摘要的 QMT 部署包

pre_release_validation/
├── tests/test_bigqmt_*.py                # 单元/契约/状态机测试
├── focus_tests/test_bigqmt_*.py          # 生命周期与故障注入
└── release_gate.py                       # 纳入新测试和配置检查
```

`bigqmt_runtime` 不得 import `sartre_core`。当前项目要求 Python 3.11，而大 QMT 官方快速入门仍以较老的内置 Python 为基线；实际版本必须通过探针确认。两边只共享 SQLite schema 和 JSON 字段约定，不共享运行时 Python 对象。

## 5. 进程与责任边界

| 能力 | 外部 FINITUDE / SARTRE | 大 QMT 薄执行端 |
|---|---:|---:|
| 历史数据、排名、指标 | 是 | 否 |
| 策略信号与目标持仓 | 是 | 否 |
| 策略级风控 | 是 | 否 |
| 单次/两次下单政策 | 是 | 否 |
| 命令持久化与等待回报 | 是 | 消费/回写 |
| 实时账户、持仓、Tick | 读取归一化快照 | 采集并发布 |
| 送单与撤单 | 仅写命令 | `passorder` / `cancel` |
| 独立硬资金上限 | 无权提高 | 是 |
| 券商原始结构归一化 | 否 | 是 |
| 启动对账 | 发起并验证 | 查询并发布 |
| 人工总开关 | 读取状态 | 本地控制 |

大 QMT 线程上不得 `sleep`、长时间轮询、跑策略计算或持有长锁。官方 FAQ 说明同一客户端内的 QMT 策略调用运行在线程模型约束下，阻塞会影响其他回调。QMT 每次定时回调只处理一个小批次，建议最多 10 条命令，单次 SQLite 事务目标小于 50 ms。

## 6. 内部对象与跨进程对象

### 6.1 不直接序列化现有 `ExecutionRequest`

当前 `ExecutionRequest` 包含 `Signal`、`StrategyContext`、`MarketSnapshot`、窗口对象和 broker-specific 整数，不适合跨进程，也不适合作为长期协议。

保留它作为引擎内部请求；在策略风控完成后，转换为稳定的 `BrokerOrderIntent`：

```python
@dataclass(frozen=True)
class BrokerOrderIntent:
    schema_version: int
    request_id: str
    strategy_id: str
    execution_module: str
    order_policy: str
    instrument_type: str       # ETF / EQUITY / REVERSE_REPO
    symbol: str
    side: str                  # BUY / SELL / REVERSE_REPO
    quantity: int              # 本次委托增量
    target_volume: int         # 决策后的目标持仓，便于对账
    price_mode: str            # LIMIT / LATEST / AFTER_HOURS_FIXED
    limit_price: Optional[str]  # 十进制定点字符串，例如 "4.213"
    reason: str
    created_at: str            # UTC RFC3339
    not_before_at: str
    expires_at: str
    expected_position: int
    expected_available_volume: int
    snapshot_observed_at: str
    account_scope: str         # 账户指纹，不是原始账号
```

协议要求：

- 枚举写字符串，不把 `23/24/11` 泄漏到引擎；
- 数量必须是整数；金额用十进制定点字符串或整数分，不用二进制浮点做摘要；
- JSON 使用 UTF-8、排序键、固定分隔符生成 canonical payload；
- `payload_sha256` 覆盖所有会影响送单的字段；
- 协议版本不认识时双方都拒绝，不做静默兼容；
- Broker 订单号、成交号、请求号统一按字符串处理，不能继续假设为 `int`。

### 6.2 请求 ID 与尝试 ID

建议逻辑请求 ID：

```text
ETFROT|20260910|CLOSE|510300.SH|TARGET=500
```

尝试 ID：

```text
ETFROT|20260910|CLOSE|510300.SH|TARGET=500:A1
ETFROT|20260910|CLOSE|510300.SH|TARGET=500:A2
```

现有 `{date}|{strategy}|{module}|{symbol}` 可作为兼容输入，但新 ID 必须加入目标持仓或决策版本，避免“同一键、不同目标”的静默冲突。

写入命令时：

- 同一 `request_id + attempt_no + command_type`、相同摘要：返回已有记录；
- 同一唯一键、不同摘要：标为 `IDEMPOTENCY_CONFLICT`，停止该策略；
- A2 只能由明确的 OrderPolicy 决策创建，不能由 IPC 超时自动创建。

### 6.3 QMT remark token

完整 request ID 保存在 SQLite。传入 `userOrderId` 的 remark 使用确定性短 token：

```text
S + Base32(SHA256(attempt_id))[:20]
```

例如 `S4Y2...`，只用大写 ASCII，目标长度不超过 21 字符。这样可适配不同 QMT/券商版本对备注长度的差异。Phase 0 必须验证备注在订单回调、成交回调和查询中的原样往返；验证失败则不得上线。

## 7. SQLite Bridge 设计

### 7.1 文件位置与连接参数

建议运行目录：

```text
C:\quant\FINITUDE_RUNTIME\bigqmt\
├── bridge.sqlite3
├── audit\YYYY-MM-DD\commands.jsonl
├── audit\YYYY-MM-DD\events.jsonl
└── backup\
```

约束：

- 必须是本机 NTFS，不放网盘、网络盘或同步目录；
- 外部引擎和 QMT 使用同一个绝对路径；
- 每次连接设置 `busy_timeout=3000`、`foreign_keys=ON`；
- Phase 0 压测通过后才启用 WAL；若 QMT 自带 sqlite 版本或杀毒软件与 WAL 不兼容，使用默认 rollback journal；
- 不依赖 SQLite JSON1 扩展，payload 只按 TEXT 保存；
- 每日备份只能在无写事务时使用 SQLite backup API，禁止直接复制活跃数据库文件。

### 7.2 最小表结构

```sql
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    command_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    attempt_no INTEGER NOT NULL CHECK (attempt_no >= 1),
    command_type TEXT NOT NULL CHECK (command_type IN ('SUBMIT', 'CANCEL')),
    related_command_id TEXT,
    schema_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    remark_token TEXT,
    state TEXT NOT NULL,
    broker_order_id TEXT,
    owner_instance_id TEXT,
    trade_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    not_before_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    claimed_at TEXT,
    submitting_at TEXT,
    acknowledged_at TEXT,
    terminal_at TEXT,
    last_error_code TEXT,
    last_error_text TEXT,
    UNIQUE (request_id, attempt_no, command_type),
    UNIQUE (remark_token),
    FOREIGN KEY (related_command_id) REFERENCES commands(command_id)
);

CREATE INDEX IF NOT EXISTS idx_commands_poll
ON commands(state, not_before_at, expires_at, created_at);

CREATE INDEX IF NOT EXISTS idx_commands_broker_order
ON commands(broker_order_id);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    request_id TEXT,
    attempt_no INTEGER,
    remark_token TEXT,
    broker_order_id TEXT,
    broker_trade_id TEXT,
    broker_status TEXT,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_request
ON events(request_id, attempt_no, observed_at);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_kind TEXT NOT NULL,
    snapshot_key TEXT NOT NULL,
    generation INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    source_at TEXT,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_kind, snapshot_key)
);

CREATE TABLE IF NOT EXISTS heartbeats (
    component TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    armed INTEGER NOT NULL CHECK (armed IN (0, 1)),
    last_seen_at TEXT NOT NULL,
    last_error_code TEXT,
    last_error_text TEXT
);
```

生产实现还应给所有状态迁移写一条 append-only event，不能只覆盖 `commands.state`。

`remark_token` 只写在 `SUBMIT` 命令；`CANCEL` 命令通过 `related_command_id` 和 `broker_order_id` 指向原提交，`remark_token` 留空。SQLite 允许 UNIQUE 列存在多个 `NULL`，不会因此阻塞多个撤单命令。

### 7.3 命令状态机

```text
PENDING
  ├─ 过期/风控失败 ───────────────→ REJECTED_LOCAL
  └─ 原子抢占 ─→ CLAIMED ─→ VALIDATING
                            ├──────→ REJECTED_LOCAL
                            ├ dry ─→ WOULD_SUBMIT
                            └──────→ SUBMITTING
                                         ├ 回调/查询匹配 → ACKNOWLEDGED
                                         │                    ├→ PARTIAL_FILLED
                                         │                    ├→ FILLED
                                         │                    ├→ CANCEL_PENDING → CANCELED
                                         │                    └→ REJECTED_BROKER
                                         └ 无法判定 ─────────→ UNKNOWN
```

终态为 `WOULD_SUBMIT`、`REJECTED_LOCAL`、`FILLED`、`CANCELED`、`REJECTED_BROKER`。`UNKNOWN` 不是成功终态，而是冻结状态：禁止同策略/同标的后续送单，直到人工对账并写入明确的 reconciliation event。

原子抢占示意：

```sql
BEGIN IMMEDIATE;
UPDATE commands
SET state = 'CLAIMED', owner_instance_id = ?, claimed_at = ?
WHERE command_id = ? AND state = 'PENDING';
COMMIT;
```

必须检查受影响行数为 1；否则说明已被其他实例处理。

## 8. 大 QMT 执行端

### 8.1 API 映射

第一版固定在 `bigqmt_runtime/mapper.py`：

| Broker-neutral 意图 | 大 QMT 映射 |
|---|---|
| 股票/ETF 买入 | `opType=23` |
| 股票/ETF 卖出 | `opType=24` |
| 单账户单证券、按股/份 | `orderType=1101` |
| 最新价 | `prType=5` |
| 固定价 | `prType=11` |
| 盘后固定价 | `prType=49` |
| timer/callback 中即时发单 | `quickTrade=2` |
| 关联 token | `userOrderId=remark_token` |

逆回购在当前 MiniQMT 中走“卖出”。迁到具体券商的大 QMT 后是否仍应使用 `opType=24`、`orderType=1101`，以及沪深品种的数量单位和价格语义，必须用 `204001.SH`、`131810.SZ` 分别做 Phase 0 探针；没有探针结果前不能把推测写成生产常量。

### 8.2 薄策略骨架

以下只是调用结构，不包含真实账号和券商版本特有字段：

```python
# coding: gbk

ACCOUNT_ID = "从本机私有设置加载"


def init(C):
    C.set_account(ACCOUNT_ID)
    bridge_initialize()
    C.run_time("bridge_tick", "1nSecond", "1970-01-01 00:00:00")


def handlebar(C):
    pass


def bridge_tick(C):
    publish_heartbeat(C)
    publish_account_position_order_snapshots(C)
    for command in claim_due_commands(limit=10):
        process_command(C, command)


def process_command(C, command):
    decision = hard_risk_validate(C, command)
    if not decision["allowed"]:
        reject_local(command, decision)
        return
    if not REAL_ORDER_ARMED:
        mark_would_submit(command, decision)
        return

    # 先落盘；从这一刻起，即便异常也禁止盲目重发。
    mark_submitting(command)
    passorder(
        decision["op_type"],
        decision["order_type"],
        ACCOUNT_ID,
        command["symbol"],
        decision["price_type"],
        decision["price"],
        decision["quantity"],
        command["strategy_id"],
        2,
        command["remark_token"],
        C,
    )


def order_callback(C, orderInfo):
    append_normalized_order_event(orderInfo)


def deal_callback(C, dealInfo):
    append_normalized_deal_event(dealInfo)


def orderError_callback(C, orderError):
    append_normalized_error_event(orderError)


def account_callback(C, accountInfo):
    append_account_event(accountInfo)


def stop(C):
    # 此时交易连接可能已不可用；只写停止状态，不在这里撤单。
    mark_gateway_stopped()
```

外部 Gateway 可以按 100–250 ms 轮询 SQLite 并等待结果；这个等待发生在外部 Python，不得发生在 QMT 回调中。

### 8.3 归一化字段

大 QMT 原始 `m_*` 对象只在 `normalizer.py` 出现。至少归一化：

| 类型 | 稳定字段 |
|---|---|
| Account | `balance`, `available_cash`, `frozen_cash`, `account_status`, `observed_at` |
| Position | `symbol`, `total_volume`, `available_volume`, `market_value`, `last_price` |
| Order | `broker_order_id`, `remark_token`, `symbol`, `side`, `original_qty`, `filled_qty`, `remaining_qty`, `limit_price`, `status` |
| Trade | `broker_trade_id`, `broker_order_id`, `remark_token`, `symbol`, `qty`, `price`, `side` |
| Tick/Instrument | `symbol`, `last`, `bid1`, `ask1`, `pre_close`, `upper_limit`, `lower_limit`, `price_tick`, `market_status`, `source_at` |

原始 payload 也要完整保存到 `events.payload_json`，但策略层只能读取归一化字段。

`get_full_tick()` 提供最新价、前收、盘口和证券状态；涨跌停价及最小变动价应优先从 `get_instrument_detail()`（旧版本名为 `get_instrumentdetail()`）取得。不能只按前收和板块比例自行推算涨跌停，否则 ST、上市初期和特殊证券会产生错误。任一关键字段取不到时拒单。

官方订单状态至少按下表映射，并用实际券商回报做契约测试：

| 原始状态 | 归一化状态 |
|---:|---|
| 49 | `PENDING_ACK` |
| 50 | `ACKNOWLEDGED` |
| 51 | `CANCEL_PENDING` |
| 52 | `PARTIAL_CANCEL_PENDING` |
| 53 | `PARTIAL_CANCELED` |
| 54 | `CANCELED` |
| 55 | `PARTIAL_FILLED` |
| 56 | `FILLED` |
| 57 | `REJECTED_BROKER` |

## 9. BigQMTOrderPolicyGateway

保留现有 `SingleSubmitPolicy` 和 `TwoSubmitPolicy`，实现新的 Gateway：

```python
class BigQMTOrderPolicyGateway:
    def submit(self, request, attempt_no):
        # request → BrokerOrderIntent → commands INSERT
        # 等待回调/查询确认；返回 string broker_order_id
        ...

    def inspect(self, broker_order_id, request):
        # 从 events/snapshots 聚合当前状态
        ...

    def wait(self, broker_order_id, timeout_seconds):
        # 外部进程可以短 sleep；超时不代表可重发
        ...

    def cancel_and_confirm(self, broker_order_id, request):
        # 写 CANCEL 命令，等待明确 CANCELED/已成交
        ...
```

需要同步修改现有协议：

- `broker_order_id: Optional[int]` → `Optional[str]`；
- `request_ids: tuple[int, ...]` → `tuple[str, ...]`；
- `price_type: Optional[int]` → broker-neutral `PriceMode`；
- 从 request metadata 删除 `broker_action` 等 MiniQMT 常量。

单次提交建议等待最多 8 秒获得明确 ACK；超过 8 秒进入 reconciliation，不能直接变成第二次提交。两次提交策略只有在第一单明确撤成、明确剩余数量、重新获取新鲜账户/持仓/委托快照后，才能创建 A2。

## 10. 大 QMT 独立硬风控

### 10.1 本机私有配置

建议初始配置：

```python
REAL_ORDER_ARMED = False
EXPECTED_ACCOUNT_FINGERPRINT = "本机生成，不存原账号"
ALLOWED_STRATEGIES = ("etf_rotation", "high_dividend_bond", "reverse_repo")
ALLOWED_INSTRUMENT_TYPES = ("ETF", "REVERSE_REPO")

MAX_MANAGED_EXPOSURE = 5000.00
MAX_SINGLE_ORDER_NOTIONAL = 1500.00
MAX_ACCEPTED_ORDERS_PER_DAY = 6

MAX_COMMAND_AGE_SECONDS = 10
MAX_QUOTE_AGE_SECONDS = 3
MAX_ACCOUNT_SNAPSHOT_AGE_SECONDS = 5
MAX_POSITION_SNAPSHOT_AGE_SECONDS = 5
MAX_HEARTBEAT_AGE_SECONDS = 3
```

上述 5000/1500/6 是小资金试运行建议值，必须由账户所有者在本机配置中显式确认。外部引擎只能请求更低上限，不能提高这些值。提高上限必须修改大 QMT 本机配置、重启并重新执行 preflight。

### 10.2 每张订单的强制检查顺序

1. `REAL_ORDER_ARMED` 为真，gateway 模式为 `LIVE`；
2. QMT 账户指纹与外部期望一致；
3. bridge、账户、持仓、委托、Tick 均新鲜；
4. command 未过期，时钟偏差在阈值内；
5. schema、摘要、remark token 全部匹配；
6. strategy、instrument、symbol 位于白名单；
7. 当前交易日、会话和证券交易状态允许；
8. 数量、最小单位、可卖数量、T+1 约束正确；
9. 买单现金充足；卖单可用持仓充足；
10. 没有同 request、同 remark、同策略标的的活动订单或不确定订单；
11. 单笔金额不超限；
12. 当日已受理单数不超限；
13. 管理范围内持仓市值 + 活动买单 + 本地 `SUBMITTING/UNKNOWN` 买单的保守敞口不超限；
14. 价格、涨跌停、盘口和会话特定规则通过；
15. 重新读取一次最关键快照，再送单。

任何数据缺失、查询异常、空回报或歧义都拒绝送单。

### 10.3 价格检查必须按会话区分

- 连续竞价：检查最新价、买一卖一、涨跌停及适用的价格笼子；
- 收盘集合竞价：沿用现有“买用上限、卖用下限”的可成交限价思路时，要按交易所和品种验证，不能套用连续竞价的 2% 检查；
- 盘后固定价格：使用 `prType=49`，独立校验会话和参考价格；
- Tick 过期或盘口无效：拒单，不使用陈旧本地价兜底。

### 10.4 逆回购使用独立额度模型

逆回购不是股票敞口，不直接套用 `MAX_MANAGED_EXPOSURE`。单独配置：

- `MAX_REPO_NOTIONAL`；
- `KEEP_CASH`；
- `MAX_REPO_ORDERS_PER_DAY`；
- 允许代码白名单；
- 15:15–15:30 的最终送单窗口；
- 沪深最小数量和步长；
- 最终送单锁内重新查询可用资金和报价。

现有逆回购的“提交锁内重查现金、重建计划、15:30 边界复核”应原样保留到 broker-neutral coordinator。

## 11. 幂等与启动对账

### 11.1 送单算法

```text
外部引擎 INSERT PENDING（唯一约束）
→ QMT 原子 CLAIM
→ 先查询当日 ORDER/DEAL 是否已有相同 remark_token
    ├ 有：关联 broker_order_id，不再送单
    └ 无：本地硬风控
          → 事务写 SUBMITTING
          → passorder
          → 等回调/查询确认
```

`passorder` 前写 `SUBMITTING` 是关键崩溃边界。若进程在调用后、回写前崩溃，重启时只能按 remark 查询，不能因为数据库没有订单号就重发。

### 11.2 启动顺序

大 QMT 启动：

1. 打开并校验 schema；
2. 发布 `STARTING/armed=0` 心跳；
3. 拉取当日 ACCOUNT、POSITION、ORDER、DEAL；
4. 按 broker order ID、trade ID、remark 去重写入事件；
5. 处理遗留 `CLAIMED/SUBMITTING/CANCEL_PENDING`；
6. 等待本地缓存稳定窗口；
7. 无歧义则发布 `READY`；有歧义则发布 `DEGRADED/armed=0`。

外部引擎启动：

1. 检查 schema 和 DB 可写；
2. 检查 QMT 心跳、实例 ID、模式、账户指纹；
3. 读取券商快照并覆盖本地执行视图；
4. 对账本地未完成请求；
5. 检查无 `UNKNOWN`、无 payload conflict；
6. 运行强制 preflight；
7. 只在全部通过后开始生成 live 命令。

### 11.3 对账优先级

```text
成交回报 > 委托回报 > 当日查询快照 > 本地命令状态
```

实际持仓和可用数量以券商快照为准；FINITUDE 本地状态只用于发现差异，不能覆盖券商状态。

## 12. 现有代码的具体拆改顺序

### Work Package 0：冻结基线与探针

改动：

- 新建 `bigqmt_runtime/probe_strategy.py`；
- 新建 `docs/BIGQMT_PROBE_RESULTS.md`；
- 记录大 QMT 客户端版本、内置 Python、sqlite3 版本、策略目录编码和写权限；
- 验证 `run_time`、`get_full_tick`、`get_trade_detail_data` 和所有回调；
- 默认 `ALLOW_PROBE_ORDER=False`，真实测试单需本机手工解锁。

探针验收：

- 账户、持仓、委托、成交字段样本已脱敏保存为 fixture；
- remark 在 order/deal/query 三处可关联；
- `passorder` 后 ACK 延迟分布有记录；
- 撤单结果与最终状态区分正确；
- 沪深 ETF 各一次最小合法委托/撤单测试；
- 沪深逆回购单位、方向、报价含义已用该券商版本确认；
- 外部 `xtdata` 停权后可用性有明确结论。

### Work Package 1：协议与 SQLite

改动：

- 新建 `broker_contracts.py`、`schema.sql`、`sqlite_bridge.py`、`state_machine.py`；
- 将 broker ID 类型改为字符串；
- canonical JSON、摘要、request/attempt/remark 生成器；
- 冲突检测、事务抢占、事件去重、心跳和快照 API。

验收：

- 两个并发消费者只能有一个 claim 成功；
- 同 payload 重放不新增订单；不同 payload 使用同 ID 必须报错；
- 任意非法状态跳转被拒绝；
- 杀进程后 DB 可恢复，无半写 JSON；
- QMT 内置 Python 能编译并读写同一数据库。

部署不直接手工修改仓库源文件。`tools/build_bigqmt_bundle.py` 应生成只读发布目录，包含 `release_id`、源文件 SHA-256 和 schema version；心跳也发布该 `release_id`。若 Phase 0 证明 QMT 策略目录不能稳定导入同目录模块，则构建脚本生成单文件 bundle，生成物不回写源文件并加入 `.gitignore`。

### Work Package 2：大 QMT 只读端

改动：

- 实现 heartbeat、ACCOUNT、POSITION、ORDER、DEAL、Tick 快照；
- 实现 normalizer 和原始事件保存；
- 外部 `bigqmt_market_account.py` 读取并生成现有 RiskManager 所需 context。

验收：

- 连续至少一个完整交易时段心跳稳定；
- 与 MiniQMT 同账户资产、持仓、可用数量逐项对比；
- 快照过期、QMT 退出、DB busy 均能让外部端 fail-closed；
- 只读阶段代码路径中不存在 `passorder` 的可达调用。

### Work Package 3：Dry Run 执行闭环

改动：

- 实现 `BigQMTOrderPolicyGateway`；
- 抽出 `ClosingAuctionCoordinator`；
- `run_bigqmt_dry_run.py` 使用真实策略、真实快照、真实硬风控；
- QMT 只记录 `WOULD_SUBMIT`，绝不调用 `passorder`。

验收：

- ETF 和高股息债对同一输入产生与现有路径相同的 target position；
- command、risk decision、WOULD_SUBMIT、策略日志可由 request ID 串联；
- 重启双方不会新增重复 intent；
- 至少覆盖 3 个实际交易时段；若月底前交易日不足，不得降低门槛，改用人工交易作为过渡。

### Work Package 4：小资金股票/ETF 实盘

改动：

- `REAL_ORDER_ARMED` 由本机手工开启；
- 开启 P0 两条收盘集合竞价链路；
- 强制 5000/1500/6 试运行上限；
- 上线取消、回调、部分成交和 reconciliation。

验收：

- 最小合法订单能明确关联 request → command → broker order → trade；
- 撤单只有在最终状态明确后才算成功；
- 部分成交后剩余数量计算正确；
- 外部引擎和 QMT 分别在 `PENDING/CLAIMED/SUBMITTING/ACKNOWLEDGED` 故障注入后均无重复订单；
- 任何 `UNKNOWN` 自动解除 armed 并阻止后续订单。

### Work Package 5：逆回购与正式切换

改动：

- 从 `miniqmt_reverse_repo_mixin.py` 抽出 `ReverseRepoCoordinator`；
- `run_miniqmt_reverse_repo.py` 的调度语义迁入 broker-independent runner；
- 使用独立 repo 风控配置和 mapper；
- 把新测试加入 `pre_release_validation/release_gate.py` 与 manifest。

验收：

- 沪深两个品种分别完成 probe；生产只启用已验证品种；
- 保留现金、数量步长、报价选择和 15:30 边界测试全部通过；
- 当日已有逆回购成交/活动委托时不会重复提交；
- 日报继续能识别逆回购订单和成交。

### Work Package 6：解开 `run_unified` 的 MiniQMT 绑定

P0 不要求一次性重构完所有 mixin。先定义小接口：

```python
class RealtimeBrokerServices(Protocol):
    def initialize(self) -> None: ...
    def stop(self) -> None: ...
    def heartbeat(self) -> BrokerHealth: ...
    def account_snapshot(self) -> AccountSnapshot: ...
    def positions_snapshot(self) -> Sequence[PositionSnapshot]: ...
    def market_snapshot(self, symbols) -> Mapping[str, MarketSnapshot]: ...
    def order_gateway(self) -> OrderPolicyGateway: ...
```

然后让 `run_unified.py` 接收服务实例，不再内部固定构造 `MiniQMTAdapter`。先接入 closing auction，其他执行模块后续逐个抽离。

## 13. 测试方案

### 13.1 单元测试

- wire DTO 序列化/反序列化和版本拒绝；
- 金额 canonicalization 和 SHA-256；
- request ID、attempt ID、remark token；
- SQLite 抢占、busy、重复事件、非法迁移；
- mapper 和所有原始状态映射；
- account/position/order/deal/tick normalizer；
- 硬风控的每一条拒绝原因；
- 价格会话分流；
- string broker ID 的兼容修改。

### 13.2 QMT 模拟器集成测试

用一个不依赖 QMT 的 fake gateway process 读写同一 SQLite，注入：

- ACK 延迟；
- 回调先于查询、查询先于回调；
- 重复回调；
- 部分成交；
- 撤单时成交；
- 拒单和错误回调；
- `passorder` 后进程崩溃；
- DB busy/locked；
- 心跳、账户、持仓或 Tick 过期；
- remark 缺失/截断；
- 外部引擎或 QMT 在每个非终态重启。

### 13.3 兼容性测试

- `bigqmt_runtime` 使用探针确认的 QMT Python 版本执行 `compileall`；
- 不使用 dataclass、match、`X | None`、新式泛型等超出该版本的语法；
- 只依赖标准库；
- 中文日志和策略文件编码在 QMT 中实测；
- DB schema 同时由 Python 3.11 和 QMT Python 读写。

### 13.4 建议验证命令

```powershell
python -m pytest -q
python pre_release_validation/release_gate.py
python -m compileall sartre_core run pre_release_validation
```

另加一个使用大 QMT 实际 Python 可执行文件的兼容命令，路径由 probe 结果确定，不能写死在仓库。

## 14. 上线验收门槛

以下全部通过才可将 `REAL_ORDER_ARMED=True`：

1. 相同输入下，Backtrader/现有实盘逻辑/新引擎得到相同 target position；
2. 每个 ExecutionRequest 唯一，同 ID 异 payload 会硬失败；
3. FINITUDE 重启不会重复下单；
4. 大 QMT 重启不会重复下单；
5. 部分成交、撤单中成交、撤成后重报均正确；
6. T+1 可用数量和现金冻结正确；
7. 券商实际持仓可覆盖/纠正 FINITUDE 本地状态；
8. 未完成订单能在启动时恢复；
9. QMT、DB 或行情失联会在阈值内 fail-closed；
10. 硬资金上限无法从外部提高；
11. 日志可按 request ID 串起 signal → intent → risk → order → trade → position；
12. 无未处理 `UNKNOWN`、无未解释持仓差异、无未关联券商订单；
13. 生产交易路径不再使用 `XtQuantTrader`；
14. 执行前 Tick、账户和持仓来自大 QMT 已验证快照；
15. release gate 全绿并生成带时间戳的审计包。

## 15. 2026-09-10 至月底排期

日期是代码交付目标；涉及真实市场的验收按实际交易时段计数。

| 日期 | 交付物 | Go/No-Go 条件 |
|---|---|---|
| 09-10～09-12 | 基线冻结、API probe、脱敏 fixtures、外部 xtdata 结论 | remark、回调、账户/持仓、ETF、逆回购任一关键项不清楚则 No-Go |
| 09-13～09-15 | contracts、schema、SQLite client、状态机、单元测试 | 并发 claim、摘要冲突、崩溃恢复通过 |
| 09-16～09-17 | QMT heartbeat/snapshot/normalizer，只读 bridge | 完整交易时段稳定、与现有账户视图一致 |
| 09-18～09-20 | BigQMT Gateway、hard risk、QMT dry executor | `passorder` 默认不可达；故障注入通过 |
| 09-21～09-23 | ClosingAuctionCoordinator、两条 P0 策略 Dry Run | 真实输入 target/intents 一致，无重复 |
| 09-24～09-26 | 小资金 ETF/债券链路、取消/部分成交/重启演练 | 5000/1500/6 下闭环审计，无 UNKNOWN |
| 09-27～09-28 | ReverseRepoCoordinator 与券商实测 | 方向、单位、报价、时间窗全部确认 |
| 09-29 | 正式切换演练、备份、kill switch、人工回退演练 | release gate 和人工检查表全绿 |
| 09-30 前 | 切换或进入人工交易保底 | 不因期限跳过安全门槛 |

若实际交易日不足以完成 Dry Run 或小资金验证，09-30 后的安全方案是“FINITUDE 继续产出目标持仓 + 人工在大 QMT 下单”，而不是把未经验证的自动送单直接上线。

## 16. 运行手册

### 16.1 每日启动

1. 启动大 QMT 并登录正确账户；
2. 启动 Bridge 策略，确认 `STARTING → READY`；
3. 检查账户指纹、时间、交易日、资金/持仓/活动委托；
4. 确认无 `UNKNOWN`、无未关联委托；
5. 运行 `run_bigqmt_live.py --preflight-only`；
6. 手工确认本地资金上限和 symbol 白名单；
7. 按需开启 `REAL_ORDER_ARMED`；
8. 启动 FINITUDE；
9. 第一张单必须人工观察 command、QMT 委托和券商回报三方一致。

### 16.2 紧急停机

1. 先将大 QMT 本地 `REAL_ORDER_ARMED=False` 或触发 kill switch；
2. 停止外部引擎继续创建命令；
3. 不依赖 QMT `stop()` 回调撤单；
4. 在大 QMT 委托界面人工检查并处置活动订单；
5. 保存账户、持仓、委托、成交和 Bridge 数据库快照；
6. 执行 reconciliation，未明确前保持 `DEGRADED/armed=0`。

### 16.3 回退

在 MiniQMT 尚可用的并行期，可回退到原执行端，但必须先证明大 QMT 没有活动或不确定订单。MiniQMT 停用后，回退目标只能是人工大 QMT 下单，不得假定可重新启用 MiniQMT。

## 17. 配置与安全整改

当前提交配置中存在非空账户标识，与仓库所声明的“敏感配置只放本机 local config”原则不一致。迁移时同时整改：

- `base_config.json` 恢复为空账号/无机器绝对路径的可提交模板；
- 真实账号、QMT 路径、Bridge 路径写入已忽略的 `local_config.json` 或 `bigqmt_runtime/local_settings.py`；
- 若仓库曾被共享，检查 Git 历史并按风险决定是否更换/清理相关标识；
- 日志和 SQLite 对外导出前脱敏账号、股东号、柜台错误详情；
- 大 QMT 和外部引擎互相只校验账户指纹，不在 IPC payload 重复传播原始账号；
- `.gitignore` 增加 `bridge.sqlite3*`、QMT 私有配置、审计包和临时备份。

`run_bigqmt_live.py` 必须自动执行现有风险预检逻辑，不再依赖操作者记得手动运行 `run_risk_check.py`。

## 18. 最小可交付定义

到 9 月底，“迁移完成”不是指所有 MiniQMT 文件都删除，而是：

- 两条收盘集合竞价策略和逆回购能通过统一 Bridge 执行；
- 生产送单、撤单、账户、持仓和执行 Tick 均不依赖 `XtQuantTrader`；
- 历史数据和策略核心未被平台 API 污染；
- 双重风控、幂等、心跳、对账、审计和人工停机均可用；
- 大 QMT 或 FINITUDE 任一端重启都不会盲目重复送单；
- 无法判定的状态自动停单；
- 未完成自动化模块有明确的人工操作路径。

完成 P0 后，再按以下顺序演进：连续竞价 → 近似盘中收盘 → 盘后固定价格 → 替换 16:00 数据刷新 → 评估是否需要 socket/HTTP。没有性能数据证明 SQLite 不够用之前，不升级 IPC 复杂度。

## 19. 官方接口依据

- [大 QMT 交易函数：`passorder`、`cancel`、`get_trade_detail_data`](https://dict.thinktrader.net/innerApi/trading_function.html)
- [大 QMT 回调函数：账户、委托、成交、错误回调](https://dict.thinktrader.net/innerApi/callback_function.html)
- [大 QMT 系统函数：`run_time` 等调度接口](https://dict.thinktrader.net/innerApi/system_function.html)
- [大 QMT 行情函数：`get_full_tick`、订阅接口](https://dict.thinktrader.net/innerApi/data_function.html)
- [大 QMT 枚举常量：操作、价格、委托状态](https://dict.thinktrader.net/innerApi/enum_constants.html)
- [大 QMT 数据结构：账户、持仓、委托、成交字段](https://dict.thinktrader.net/innerApi/data_structure.html)
- [大 QMT 常见问题：异步交易、缓存延迟、线程与状态注意事项](https://dict.thinktrader.net/innerApi/question_answer.html)
- [大 QMT 快速开始：内置 Python 开发模式](https://dict.thinktrader.net/innerApi/start_now.html)

---

这份方案的首个实际开发动作应是 **Work Package 0 探针**，不是先写 `passorder` 生产封装。只有实际客户端版本、回调字段、remark 往返和逆回购语义被记录为可重复测试的 fixture，后续 Mapper 与状态机才有可靠基线。
