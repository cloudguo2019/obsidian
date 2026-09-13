"""Registered Stage 8 formal-batch extensions for HD-ANCHOR-001.

This module layers the frozen P00 account semantics from ``stage8_engine`` with
the preregistered P01--P23 overlays.  It contains no file-output or lock-access
code; the separately authorized runner owns those gates.
"""

from __future__ import annotations

import copy
import csv
from bisect import bisect_left
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .stage8_engine import (
    Account,
    CorporateAction,
    DataGateError,
    FeeBreakdown,
    FillResult,
    OrderInstruction,
    PITDividendRecord,
    PITDividendSelector,
    ReconciliationError,
    Session,
    StrategyConfig,
    StrategyDecision,
    ZERO,
    account_amount,
    dec,
    fee_amount,
    parse_date,
    required_date,
    shanghai_close,
)


CENT = Decimal("0.01")
BPS_DENOMINATOR = Decimal("10000")


@dataclass(frozen=True)
class MarketSession:
    session_date: date
    open: Decimal | None
    close: Decimal | None
    trade_status: str
    limit_up: Decimal | None
    limit_down: Decimal | None


@dataclass(frozen=True)
class ProfileSpec:
    profile_id: str
    description: str
    fee_multiplier: Decimal = Decimal("1")
    execution_lag_sessions: int = 1
    fill_field: str = "close"
    adverse_execution_bps: Decimal = ZERO
    start_date: date = date(2022, 3, 10)
    pit_available_delay_sessions: int = 0
    dividend_multiplier: Decimal = Decimal("1")
    yield_shift: Decimal = ZERO
    confirmation_bars: int = 2
    dynamic_initial_shares: int = 1000
    forced_fill_mode: str | None = None
    runnable: bool = True
    not_run_reason: str | None = None


def registered_profiles() -> tuple[ProfileSpec, ...]:
    rows = (
        ProfileSpec("P00", "主规则，无压力覆盖"),
        ProfileSpec("P01", "所有非零交易费用2倍", fee_multiplier=Decimal("2")),
        ProfileSpec("P02", "所有非零交易费用3倍", fee_multiplier=Decimal("3")),
        ProfileSpec("P03", "T日信号于T+2日收盘成交", execution_lag_sessions=2),
        ProfileSpec("P04", "T日信号于T+3日收盘成交", execution_lag_sessions=3),
        ProfileSpec("P05", "T日收盘信号于T+1日开盘成交", fill_field="open"),
        ProfileSpec("P06", "单边5bp不利执行偏移", adverse_execution_bps=Decimal("5")),
        ProfileSpec("P07", "单边10bp不利执行偏移", adverse_execution_bps=Decimal("10")),
        ProfileSpec("P08", "起点顺延3自然月", start_date=date(2022, 6, 10)),
        ProfileSpec("P09", "起点顺延6自然月", start_date=date(2022, 9, 13)),
        ProfileSpec("P10", "PIT可得时间延迟1个上交所会话", pit_available_delay_sessions=1),
        ProfileSpec("P11", "PIT可得时间延迟5个上交所会话", pit_available_delay_sessions=5),
        ProfileSpec("P12", "有效Dhat乘0.9", dividend_multiplier=Decimal("0.9")),
        ProfileSpec("P13", "有效Dhat乘1.1", dividend_multiplier=Decimal("1.1")),
        ProfileSpec("P14", "有效Dhat乘0.8", dividend_multiplier=Decimal("0.8")),
        ProfileSpec("P15", "五个正股息率阈值统一减0.001", yield_shift=Decimal("-0.001")),
        ProfileSpec("P16", "五个正股息率阈值统一加0.001", yield_shift=Decimal("0.001")),
        ProfileSpec("P17", "confirmation_bars=1", confirmation_bars=1),
        ProfileSpec("P18", "confirmation_bars=3", confirmation_bars=3),
        ProfileSpec("P19", "动态账户初始化1200股", dynamic_initial_shares=1200),
        ProfileSpec("P20", "动态账户初始化0股", dynamic_initial_shares=0),
        ProfileSpec(
            "P21",
            "各账户现金按可实现券商资金利率计息",
            runnable=False,
            not_run_reason="NO_AUDITABLE_EXECUTABLE_BROKER_CASH_RATE_INPUT",
        ),
        ProfileSpec("P22", "每第10个本可完整成交父委托强制未成交", forced_fill_mode="EVERY_10TH_UNFILLED"),
        ProfileSpec("P23", "每第10个本可完整成交父委托半成交", forced_fill_mode="EVERY_10TH_HALF_FILL"),
    )
    expected = tuple(f"P{number:02d}" for number in range(24))
    if tuple(item.profile_id for item in rows) != expected:
        raise AssertionError("registered profile IDs are incomplete or out of order")
    return rows


def load_market_sessions(
    path: str | Path,
    *,
    start_inclusive: date | None = None,
    end_exclusive: date | None = None,
) -> tuple[MarketSession, ...]:
    sessions: list[MarketSession] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            session_date = required_date(row["session_date"], "session_date")
            if end_exclusive is not None and session_date >= end_exclusive:
                break
            if start_inclusive is not None and session_date < start_inclusive:
                continue
            sessions.append(
                MarketSession(
                    session_date=session_date,
                    open=dec(row["open"]) if row["open"] else None,
                    close=dec(row["close"]) if row["close"] else None,
                    trade_status=row["trade_status"],
                    limit_up=dec(row["limit_up"]) if row["limit_up"] else None,
                    limit_down=dec(row["limit_down"]) if row["limit_down"] else None,
                )
            )
    return tuple(sessions)


def load_session_dates(
    path: str | Path,
    *,
    end_exclusive: date | None = None,
) -> tuple[date, ...]:
    """Read only the date column, stopping before an unauthorized right tail."""

    dates: list[date] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            session_date = required_date(row["session_date"], "session_date")
            if end_exclusive is not None and session_date >= end_exclusive:
                break
            dates.append(session_date)
    return tuple(dates)


class ScaledTransactionCostSchedule:
    """Multiply each normally rounded non-zero transaction charge."""

    def __init__(self, base: object, multiplier: object):
        self.base = base
        self.multiplier = dec(multiplier)
        if self.multiplier <= ZERO:
            raise ValueError("fee multiplier must be positive")

    def calculate(self, session_date: date, side: str, quantity: int, price: Decimal) -> FeeBreakdown:
        normal = self.base.calculate(session_date, side, quantity, price)
        if self.multiplier == Decimal("1"):
            return normal
        return FeeBreakdown({
            name: fee_amount(value * self.multiplier)
            for name, value in normal.components.items()
            if value != ZERO
        })


class ProfilePITSelector(PITDividendSelector):
    """Apply only the registered PIT-latency and Dhat-size overlays."""

    def __init__(
        self,
        records: Iterable[PITDividendRecord],
        *,
        session_dates: Sequence[date],
        available_delay_sessions: int = 0,
        dividend_multiplier: object = "1",
    ):
        if available_delay_sessions < 0:
            raise ValueError("PIT delay must be non-negative")
        ordered_dates = tuple(sorted(set(session_dates)))
        multiplier = dec(dividend_multiplier)
        transformed: list[PITDividendRecord] = []
        for record in records:
            available = record.available_time
            if available_delay_sessions:
                position = bisect_left(ordered_dates, available.date())
                if position >= len(ordered_dates) or ordered_dates[position] != available.date():
                    raise DataGateError(f"PIT available date is not an SSE session: {record.record_id}")
                delayed_position = position + available_delay_sessions
                if delayed_position >= len(ordered_dates):
                    raise DataGateError(f"PIT delay exceeds calendar: {record.record_id}")
                available = datetime.combine(
                    ordered_dates[delayed_position], available.timetz()
                )
            transformed.append(replace(
                record,
                available_time=available,
                dps=record.dps * multiplier,
            ))
        super().__init__(transformed)


def shifted_strategy_config(shift: object = "0") -> StrategyConfig:
    delta = dec(shift)
    base = StrategyConfig()
    buy = {shares: threshold + delta for shares, threshold in base.buy_yields.items()}
    sell = {shares: threshold + delta for shares, threshold in base.sell_yields.items()}
    if any(value <= ZERO for value in (*buy.values(), *sell.values())):
        raise ValueError("yield shift creates a non-positive threshold")
    return replace(base, buy_yields=buy, sell_yields=sell)


class ProfileStrategy:
    """The frozen HDAnchor state machine generalized to 1/2/3 confirmations."""

    def __init__(self, config: StrategyConfig, confirmation_bars: int):
        if confirmation_bars not in {1, 2, 3}:
            raise ValueError("only preregistered confirmation counts are allowed")
        self.config = config
        self.confirmation_bars = confirmation_bars

    def decide(
        self,
        *,
        shares: int,
        average_price: Decimal,
        total_assets: Decimal,
        confirmation_closes: Sequence[Decimal],
        dividend_dps: Decimal,
        fundamental_gate: str = "NORMAL",
    ) -> StrategyDecision:
        cfg = self.config
        if len(confirmation_closes) != self.confirmation_bars:
            return StrategyDecision(shares, "CONFIRMATION_BAR_MISSING")
        current_close = confirmation_closes[-1]
        if (
            dividend_dps <= ZERO
            or any(price <= ZERO for price in confirmation_closes)
            or total_assets <= ZERO
        ):
            return StrategyDecision(shares, "INVALID_REQUIRED_INPUT")
        if fundamental_gate == "REVIEW":
            return StrategyDecision(shares, "REVIEW_HOLD")
        if fundamental_gate == "EXIT":
            target = cfg.exit_target_shares if shares > cfg.exit_target_shares else shares
            return StrategyDecision(target, "FUNDAMENTAL_EXIT")
        if fundamental_gate not in {"NORMAL", "STOP_ADD"}:
            return StrategyDecision(shares, "UNKNOWN_FUNDAMENTAL_GATE")

        if shares > cfg.max_total_shares:
            return StrategyDecision(max(shares - cfg.step_shares, cfg.max_total_shares), "EXCESS_POSITION_CORRECTION")
        if shares not in set(range(0, cfg.max_total_shares + 1, cfg.step_shares)):
            return StrategyDecision(shares, "ILLEGAL_DISCRETE_STATE_HOLD")

        target = shares
        reason = "HOLD"
        if shares < cfg.core_shares:
            target = min(shares + cfg.step_shares, cfg.core_shares)
            reason = "CORE_BUILD"
        elif shares in cfg.buy_yields:
            boundary = dividend_dps / cfg.buy_yields[shares]
            if all(price <= boundary for price in confirmation_closes):
                target = min(shares + cfg.step_shares, cfg.max_auto_add_shares)
                reason = "ADJACENT_BUY"
        if target == shares and shares in cfg.sell_yields:
            boundary = dividend_dps / cfg.sell_yields[shares]
            if all(price >= boundary for price in confirmation_closes):
                target = max(shares - cfg.step_shares, cfg.core_shares)
                reason = "ADJACENT_SELL"

        if target > shares:
            if fundamental_gate == "STOP_ADD":
                return StrategyDecision(shares, "STOP_ADD_HOLD")
            loss_impact = min((current_close - average_price) * dec(shares), ZERO) / total_assets
            if loss_impact <= cfg.loss_stop_add:
                return StrategyDecision(shares, "ACCOUNT_LOSS_STOP_ADD")
        return StrategyDecision(target, reason)


@dataclass(frozen=True)
class BatchOrder:
    order_id: str
    signal_date: date
    signal_session_index: int
    execute_session_index: int
    original_shares: int
    target_shares: int
    reason: str
    decision_close: Decimal
    decision_dps: Decimal

    def account_instruction(self, target_shares: int | None = None) -> OrderInstruction:
        return OrderInstruction(
            order_id=self.order_id,
            signal_date=self.signal_date,
            execute_session_index=self.execute_session_index,
            original_shares=self.original_shares,
            target_shares=self.target_shares if target_shares is None else target_shares,
            reason=self.reason,
        )


@dataclass(frozen=True)
class FillAudit:
    order_id: str
    session_date: date
    session_index: int
    status: str
    reason: str
    side: str | None
    requested_quantity: int
    filled_quantity: int
    fill_price: Decimal | None
    reference_price: Decimal | None
    fees: FeeBreakdown
    deferred_tax_paid: Decimal
    pre_shares: int
    post_shares: int
    source_reason: str


@dataclass(frozen=True)
class BatchDailySnapshot:
    session_date: date
    session_index: int
    mark: Decimal
    cash: Decimal
    shares: int
    available_shares: int
    dividend_receivable: Decimal
    tax_liability: Decimal
    nav: Decimal
    price_pnl: Decimal
    execution_price_pnl: Decimal
    new_dividend_entitlement: Decimal
    dividend_paid_gross: Decimal
    tax_reserve_change: Decimal
    transaction_fees: Decimal
    expected_nav_change: Decimal
    actual_nav_change: Decimal
    reconciliation_difference: Decimal
    signal_blocker: str | None
    selected_pit_record_id: str | None
    generated_order: BatchOrder | None
    fills: tuple[FillAudit, ...]


class FormalPathEngine:
    """One dynamic or static account path under a registered profile."""

    def __init__(
        self,
        *,
        account: Account,
        initial_mark: object,
        initial_date: date,
        profile: ProfileSpec,
        pit_selector: ProfilePITSelector | None,
        strategy: ProfileStrategy | None,
        corporate_actions: Iterable[CorporateAction],
        reconciliation_tolerance: object = "0.01",
    ):
        self.account = account
        self.profile = profile
        self.pit_selector = pit_selector
        self.strategy = strategy
        self.last_mark = dec(initial_mark)
        self.previous_nav = account.nav(self.last_mark)
        self.previous_session_date = initial_date
        self.close_history: list[Decimal] = [self.last_mark]
        self.pending: dict[int, list[BatchOrder]] = {}
        self.actions = tuple(
            action for action in corporate_actions
            if action.record_status == "VALID" and action.action_type == "CASH_DIVIDEND"
        )
        self.reconciliation_tolerance = dec(reconciliation_tolerance)
        self._order_counter = 0
        self._otherwise_fillable_parent_counter = 0

    def _actions_on(self, field_name: str, session_date: date) -> list[CorporateAction]:
        return [action for action in self.actions if getattr(action, field_name) == session_date]

    def _reference_fill_price(self, session: MarketSession) -> Decimal | None:
        return session.open if self.profile.fill_field == "open" else session.close

    def _adverse_fill_price(self, reference: Decimal | None, side: str, session: MarketSession) -> Decimal | None:
        if reference is None:
            return None
        bps = self.profile.adverse_execution_bps
        if bps == ZERO:
            return reference
        if side == "BUY":
            shifted = (reference * (Decimal("1") + bps / BPS_DENOMINATOR)).quantize(
                CENT, rounding=ROUND_CEILING
            )
            return min(shifted, session.limit_up) if session.limit_up is not None else shifted
        shifted = (reference * (Decimal("1") - bps / BPS_DENOMINATOR)).quantize(
            CENT, rounding=ROUND_FLOOR
        )
        return max(shifted, session.limit_down) if session.limit_down is not None else shifted

    def execute_instruction(
        self,
        order: BatchOrder,
        session: MarketSession,
        session_index: int,
        mark: Decimal,
    ) -> tuple[FillAudit, Decimal]:
        pre_shares = self.account.shares
        delta = order.target_shares - pre_shares
        side = "BUY" if delta > 0 else "SELL" if delta < 0 else None
        reference = self._reference_fill_price(session)
        fill_price = self._adverse_fill_price(reference, side, session) if side is not None else reference
        account_session = Session(
            session_date=session.session_date,
            close=fill_price,
            trade_status=session.trade_status,
            limit_up=session.limit_up,
            limit_down=session.limit_down,
        )

        preview_account = copy.deepcopy(self.account)
        preview = preview_account.execute(order.account_instruction(), account_session, session_index)
        force = None
        if preview.status == "FILLED":
            self._otherwise_fillable_parent_counter += 1
            if self._otherwise_fillable_parent_counter % 10 == 0:
                force = self.profile.forced_fill_mode

        requested = abs(delta)
        if force == "EVERY_10TH_UNFILLED":
            result = FillResult(
                order_id=order.order_id,
                status="UNFILLED",
                reason="FORCED_EVERY_10TH_PARENT_UNFILLED",
                session_date=session.session_date,
                side=side,
                quantity=requested,
                price=fill_price,
                fees=FeeBreakdown({}),
                deferred_tax_paid=ZERO,
                pre_shares=pre_shares,
                post_shares=pre_shares,
            )
            filled_quantity = 0
        elif force == "EVERY_10TH_HALF_FILL":
            filled_quantity = requested // 2
            if filled_quantity <= 0:
                result = FillResult(
                    order.order_id, "UNFILLED", "FORCED_HALF_FILL_ROUNDED_TO_ZERO",
                    session.session_date, side, requested, fill_price, FeeBreakdown({}),
                    ZERO, pre_shares, pre_shares,
                )
            else:
                partial_target = pre_shares + filled_quantity if side == "BUY" else pre_shares - filled_quantity
                executed = self.account.execute(
                    order.account_instruction(partial_target), account_session, session_index
                )
                if executed.status != "FILLED":
                    raise ReconciliationError("previewed half-fill could not execute")
                result = FillResult(
                    executed.order_id, "PARTIAL", "FORCED_EVERY_10TH_PARENT_HALF_FILL",
                    executed.session_date, executed.side, executed.quantity, executed.price,
                    executed.fees, executed.deferred_tax_paid, executed.pre_shares, executed.post_shares,
                )
        else:
            result = self.account.execute(order.account_instruction(), account_session, session_index)
            filled_quantity = result.quantity if result.status == "FILLED" else 0

        execution_price_pnl = ZERO
        if result.status in {"FILLED", "PARTIAL"} and result.price is not None:
            quantity = dec(result.quantity)
            execution_price_pnl = account_amount(
                quantity * (mark - result.price)
                if result.side == "BUY"
                else quantity * (result.price - mark)
            )
        audit = FillAudit(
            order_id=order.order_id,
            session_date=session.session_date,
            session_index=session_index,
            status=result.status,
            reason=result.reason,
            side=result.side,
            requested_quantity=requested,
            filled_quantity=filled_quantity,
            fill_price=result.price,
            reference_price=reference,
            fees=result.fees,
            deferred_tax_paid=result.deferred_tax_paid,
            pre_shares=result.pre_shares,
            post_shares=result.post_shares,
            source_reason=order.reason,
        )
        return audit, execution_price_pnl

    def step(
        self,
        session: MarketSession,
        session_index: int,
        fundamental_gate: str = "NORMAL",
    ) -> BatchDailySnapshot:
        if session.session_date <= self.previous_session_date:
            raise DataGateError("sessions must be strictly increasing")
        opening_shares = self.account.shares
        mark = session.close if session.trade_status == "TRADING" and session.close is not None else self.last_mark
        if mark <= ZERO:
            raise DataGateError("a valid current or carry-forward mark is required")
        price_pnl = account_amount(dec(opening_shares) * (mark - self.last_mark))

        new_dividend = ZERO
        for action in self._actions_on("ex_date", session.session_date):
            new_dividend += self.account.recognize_dividend(action)
        tax_reserve_change = self.account.revalue_tax_liability(session.session_date)
        dividend_paid = ZERO
        for action in self._actions_on("pay_date", session.session_date):
            gross, _ = self.account.pay_dividend(action, session.session_date)
            dividend_paid += gross

        fills: list[FillAudit] = []
        transaction_fees = ZERO
        execution_price_pnl = ZERO
        for order in self.pending.pop(session_index, []):
            fill, fill_price_pnl = self.execute_instruction(order, session, session_index, mark)
            fills.append(fill)
            transaction_fees += fill.fees.total
            execution_price_pnl += fill_price_pnl

        for action in self._actions_on("record_date", session.session_date):
            self.account.snapshot_record_date(action)

        generated: BatchOrder | None = None
        signal_blocker: str | None = None
        selected_record_id: str | None = None
        if self.strategy is not None:
            if any(self.pending.values()):
                signal_blocker = "ORDER_PENDING_HOLD"
            elif session.trade_status != "TRADING" or session.close is None:
                signal_blocker = "NO_TRADABLE_COMPLETED_CLOSE"
            elif len(self.close_history) + 1 < self.strategy.confirmation_bars:
                signal_blocker = "CONFIRMATION_BAR_MISSING"
            elif self.pit_selector is None:
                signal_blocker = "PIT_SELECTOR_MISSING"
            else:
                pit, signal_blocker = self.pit_selector.select(shanghai_close(session.session_date))
                if pit is not None:
                    selected_record_id = pit.record_id
                    closes = (self.close_history + [session.close])[-self.strategy.confirmation_bars:]
                    decision = self.strategy.decide(
                        shares=self.account.shares,
                        average_price=self.account.average_price,
                        total_assets=self.account.nav(mark),
                        confirmation_closes=closes,
                        dividend_dps=pit.dps,
                        fundamental_gate=fundamental_gate,
                    )
                    if decision.target_shares != self.account.shares:
                        self._order_counter += 1
                        generated = BatchOrder(
                            order_id=f"ORDER-{self._order_counter:06d}",
                            signal_date=session.session_date,
                            signal_session_index=session_index,
                            execute_session_index=session_index + self.profile.execution_lag_sessions,
                            original_shares=self.account.shares,
                            target_shares=decision.target_shares,
                            reason=decision.reason,
                            decision_close=session.close,
                            decision_dps=pit.dps,
                        )
                        self.pending.setdefault(generated.execute_session_index, []).append(generated)
                    else:
                        signal_blocker = decision.reason

        nav = self.account.nav(mark)
        actual_change = account_amount(nav - self.previous_nav)
        expected_change = account_amount(
            price_pnl + execution_price_pnl + new_dividend - tax_reserve_change - transaction_fees
        )
        difference = account_amount(actual_change - expected_change)
        if abs(difference) > self.reconciliation_tolerance:
            raise ReconciliationError(
                f"{session.session_date}: reconciliation difference {difference} exceeds "
                f"{self.reconciliation_tolerance}"
            )

        snapshot = BatchDailySnapshot(
            session_date=session.session_date,
            session_index=session_index,
            mark=mark,
            cash=self.account.cash,
            shares=self.account.shares,
            available_shares=self.account.available_shares(session_index),
            dividend_receivable=self.account.dividend_receivable,
            tax_liability=self.account.tax_liability,
            nav=nav,
            price_pnl=price_pnl,
            execution_price_pnl=account_amount(execution_price_pnl),
            new_dividend_entitlement=account_amount(new_dividend),
            dividend_paid_gross=account_amount(dividend_paid),
            tax_reserve_change=tax_reserve_change,
            transaction_fees=account_amount(transaction_fees),
            expected_nav_change=expected_change,
            actual_nav_change=actual_change,
            reconciliation_difference=difference,
            signal_blocker=signal_blocker,
            selected_pit_record_id=selected_record_id,
            generated_order=generated,
            fills=tuple(fills),
        )
        self.previous_nav = nav
        self.last_mark = mark
        self.previous_session_date = session.session_date
        if session.trade_status == "TRADING" and session.close is not None:
            self.close_history.append(session.close)
            self.close_history = self.close_history[-2:]
        else:
            self.close_history.clear()
        return snapshot


@dataclass(frozen=True)
class PathPoint:
    profile_id: str
    account_id: str
    session_date: date
    session_index: int
    trade_status: str
    mark: Decimal
    cash: Decimal
    shares: int
    available_shares: int
    dividend_receivable: Decimal
    tax_liability: Decimal
    nav: Decimal
    daily_return: Decimal | None
    drawdown: Decimal
    equity_weight: Decimal
    cash_ratio: Decimal
    price_pnl: Decimal
    execution_price_pnl: Decimal
    new_dividend_entitlement: Decimal
    dividend_paid_gross: Decimal
    tax_reserve_change: Decimal
    transaction_fees: Decimal
    expected_nav_change: Decimal
    actual_nav_change: Decimal
    reconciliation_difference: Decimal
    signal_blocker: str | None
    selected_pit_record_id: str | None


def initial_path_point(
    *,
    profile_id: str,
    account_id: str,
    session: MarketSession,
    account: Account,
) -> PathPoint:
    if session.close is None:
        raise DataGateError("initial session requires a verified close")
    nav = account.nav(session.close)
    return PathPoint(
        profile_id=profile_id,
        account_id=account_id,
        session_date=session.session_date,
        session_index=0,
        trade_status=session.trade_status,
        mark=session.close,
        cash=account.cash,
        shares=account.shares,
        available_shares=account.available_shares(0),
        dividend_receivable=account.dividend_receivable,
        tax_liability=account.tax_liability,
        nav=nav,
        daily_return=None,
        drawdown=ZERO,
        equity_weight=dec(account.shares) * session.close / nav,
        cash_ratio=account.cash / nav,
        price_pnl=ZERO,
        execution_price_pnl=ZERO,
        new_dividend_entitlement=ZERO,
        dividend_paid_gross=ZERO,
        tax_reserve_change=ZERO,
        transaction_fees=ZERO,
        expected_nav_change=ZERO,
        actual_nav_change=ZERO,
        reconciliation_difference=ZERO,
        signal_blocker="INITIALIZATION_NO_SIGNAL",
        selected_pit_record_id=None,
    )


def snapshot_path_point(
    *,
    profile_id: str,
    account_id: str,
    trade_status: str,
    snapshot: BatchDailySnapshot,
    previous_nav: Decimal,
    high_water: Decimal,
) -> PathPoint:
    daily = snapshot.nav / previous_nav - Decimal("1")
    drawdown = snapshot.nav / max(high_water, snapshot.nav) - Decimal("1")
    return PathPoint(
        profile_id=profile_id,
        account_id=account_id,
        session_date=snapshot.session_date,
        session_index=snapshot.session_index,
        trade_status=trade_status,
        mark=snapshot.mark,
        cash=snapshot.cash,
        shares=snapshot.shares,
        available_shares=snapshot.available_shares,
        dividend_receivable=snapshot.dividend_receivable,
        tax_liability=snapshot.tax_liability,
        nav=snapshot.nav,
        daily_return=daily,
        drawdown=drawdown,
        equity_weight=dec(snapshot.shares) * snapshot.mark / snapshot.nav,
        cash_ratio=snapshot.cash / snapshot.nav,
        price_pnl=snapshot.price_pnl,
        execution_price_pnl=snapshot.execution_price_pnl,
        new_dividend_entitlement=snapshot.new_dividend_entitlement,
        dividend_paid_gross=snapshot.dividend_paid_gross,
        tax_reserve_change=snapshot.tax_reserve_change,
        transaction_fees=snapshot.transaction_fees,
        expected_nav_change=snapshot.expected_nav_change,
        actual_nav_change=snapshot.actual_nav_change,
        reconciliation_difference=snapshot.reconciliation_difference,
        signal_blocker=snapshot.signal_blocker,
        selected_pit_record_id=snapshot.selected_pit_record_id,
    )


def compound(values: Iterable[Decimal]) -> Decimal:
    result = Decimal("1")
    for value in values:
        result *= Decimal("1") + value
    return result - Decimal("1")


def path_metrics(
    points: Sequence[PathPoint],
    fills: Sequence[FillAudit],
    *,
    generated_order_count: int,
    pending_at_terminal: int,
    pit_valid_decision_sessions: int | None,
    pit_decision_sessions: int | None,
) -> dict[str, object]:
    if len(points) < 2:
        raise ValueError("a formal path requires at least two observations")
    initial_nav = points[0].nav
    final_nav = points[-1].nav
    elapsed_days = (points[-1].session_date - points[0].session_date).days
    elapsed_years = Decimal(elapsed_days) / Decimal("365.25")
    total_return = final_nav / initial_nav - Decimal("1")
    cagr = Decimal(str(float(final_nav / initial_nav) ** (float(Decimal("1") / elapsed_years)))) - Decimal("1")

    high = points[0].nav
    max_drawdown = ZERO
    underwater_start: int | None = None
    longest_completed = 0
    longest_completed_calendar_days = 0
    longest_completed_start: date | None = None
    longest_completed_end: date | None = None
    for index, point in enumerate(points[1:], start=1):
        if point.nav >= high:
            if underwater_start is not None:
                completed_sessions = index - underwater_start
                completed_calendar_days = (
                    point.session_date - points[underwater_start].session_date
                ).days
                if (
                    completed_sessions > longest_completed
                    or (
                        completed_sessions == longest_completed
                        and completed_calendar_days > longest_completed_calendar_days
                    )
                ):
                    longest_completed = completed_sessions
                    longest_completed_calendar_days = completed_calendar_days
                    longest_completed_start = points[underwater_start].session_date
                    longest_completed_end = point.session_date
                underwater_start = None
            high = point.nav
        else:
            if underwater_start is None:
                underwater_start = index
            max_drawdown = min(max_drawdown, point.nav / high - Decimal("1"))
    censored_sessions = len(points) - 1 - underwater_start if underwater_start is not None else 0
    censored_calendar_days = (
        (points[-1].session_date - points[underwater_start].session_date).days
        if underwater_start is not None
        else 0
    )
    if censored_sessions > longest_completed or (
        censored_sessions == longest_completed
        and censored_calendar_days > longest_completed_calendar_days
    ):
        longest_underwater = censored_sessions
        longest_underwater_calendar_days = censored_calendar_days
        longest_underwater_start = points[underwater_start].session_date
        longest_underwater_end = None
    else:
        longest_underwater = longest_completed
        longest_underwater_calendar_days = longest_completed_calendar_days
        longest_underwater_start = longest_completed_start
        longest_underwater_end = longest_completed_end
    recovery_status = (
        "FAIL_OVER_126_SESSIONS"
        if longest_underwater > 126
        else "OBSERVE_RIGHT_CENSORED"
        if underwater_start is not None
        else "PASS"
    )

    daily_returns = [item.daily_return for item in points if item.daily_return is not None]
    downside_mean = sum((min(item, ZERO) ** 2 for item in daily_returns), ZERO) / dec(len(daily_returns))
    downside_deviation = Decimal(str((float(downside_mean) * 252.0) ** 0.5))
    abs_mdd = abs(max_drawdown)
    calmar = None if abs_mdd == ZERO else cagr / abs_mdd
    average_nav = sum((item.nav for item in points), ZERO) / dec(len(points))

    executed = [item for item in fills if item.status in {"FILLED", "PARTIAL"}]
    turnover_notional = sum(
        (dec(item.filled_quantity) * item.fill_price for item in executed if item.fill_price is not None), ZERO
    )
    turnover = turnover_notional / average_nav / elapsed_years
    fee_components: dict[str, Decimal] = {}
    for fill in executed:
        for name, value in fill.fees.components.items():
            fee_components[name] = fee_components.get(name, ZERO) + value

    filled_by_index: dict[int, int] = {}
    for item in executed:
        filled_by_index[item.session_index] = filled_by_index.get(item.session_index, 0) + 1
    maximum_rolling_252 = 0
    for index in range(len(points)):
        lower = max(1, index - 251)
        maximum_rolling_252 = max(
            maximum_rolling_252,
            sum(count for fill_index, count in filled_by_index.items() if lower <= fill_index <= index),
        )

    transition_indices = sorted({
        item.session_index for item in executed
        if item.status == "FILLED" and item.source_reason in {"ADJACENT_BUY", "ADJACENT_SELL"}
    })
    clusters = 0
    previous: int | None = None
    for index in transition_indices:
        if previous is None or index - previous >= 20:
            clusters += 1
        previous = index

    return {
        "start_date": points[0].session_date.isoformat(),
        "end_date": points[-1].session_date.isoformat(),
        "session_observations": len(points),
        "elapsed_calendar_days": elapsed_days,
        "initial_nav_cny": str(initial_nav),
        "final_nav_cny": str(final_nav),
        "total_return": str(total_return),
        "cagr": str(cagr),
        "max_drawdown": str(max_drawdown),
        "longest_underwater_sessions": longest_underwater,
        "longest_underwater_calendar_days": longest_underwater_calendar_days,
        "longest_underwater_start_date": (
            None if longest_underwater_start is None else longest_underwater_start.isoformat()
        ),
        "longest_underwater_recovery_date": (
            None if longest_underwater_end is None else longest_underwater_end.isoformat()
        ),
        "underwater_right_censored": underwater_start is not None,
        "recovery_gate": recovery_status,
        "calmar": None if calmar is None else str(calmar),
        "downside_deviation": str(downside_deviation),
        "average_shares": str(sum((dec(item.shares) for item in points), ZERO) / dec(len(points))),
        "minimum_shares": min(item.shares for item in points),
        "maximum_shares": max(item.shares for item in points),
        "average_equity_weight": str(sum((item.equity_weight for item in points), ZERO) / dec(len(points))),
        "minimum_equity_weight": str(min(item.equity_weight for item in points)),
        "maximum_equity_weight": str(max(item.equity_weight for item in points)),
        "average_cash_ratio": str(sum((item.cash_ratio for item in points), ZERO) / dec(len(points))),
        "annual_turnover": str(turnover),
        "turnover_notional_cny": str(account_amount(turnover_notional)),
        "fee_components_cny": {name: str(account_amount(value)) for name, value in sorted(fee_components.items())},
        "transaction_fees_cny": str(account_amount(sum((item.transaction_fees for item in points), ZERO))),
        "new_dividend_entitlements_cny": str(account_amount(sum((item.new_dividend_entitlement for item in points), ZERO))),
        "dividend_paid_gross_cny": str(account_amount(sum((item.dividend_paid_gross for item in points), ZERO))),
        "price_pnl_cny": str(account_amount(sum((item.price_pnl for item in points), ZERO))),
        "execution_price_pnl_cny": str(account_amount(sum((item.execution_price_pnl for item in points), ZERO))),
        "net_tax_reserve_change_cny": str(account_amount(sum((item.tax_reserve_change for item in points), ZERO))),
        "generated_parent_orders": generated_order_count,
        "filled_parent_orders": sum(item.status == "FILLED" for item in fills),
        "partially_filled_parent_orders": sum(item.status == "PARTIAL" for item in fills),
        "unfilled_parent_orders": sum(item.status == "UNFILLED" for item in fills),
        "pending_parent_orders_at_terminal": pending_at_terminal,
        "maximum_filled_parent_orders_in_rolling_252_sessions": maximum_rolling_252,
        "filled_adjacent_state_transition_days": len(transition_indices),
        "transition_clusters_20_session_gap": clusters,
        "pit_valid_decision_sessions": pit_valid_decision_sessions,
        "pit_decision_sessions": pit_decision_sessions,
        "pit_coverage_ratio": (
            None
            if pit_decision_sessions in {None, 0}
            else str(dec(pit_valid_decision_sessions) / dec(pit_decision_sessions))
        ),
        "maximum_absolute_daily_reconciliation_cny": str(
            max(abs(item.reconciliation_difference) for item in points)
        ),
    }


def window_effects(
    dynamic: Sequence[PathPoint],
    comparator: Sequence[PathPoint],
    windows: Sequence[Mapping[str, str]],
) -> list[dict[str, object]]:
    dynamic_returns = {
        item.session_date: item.daily_return for item in dynamic if item.daily_return is not None
    }
    comparator_returns = {
        item.session_date: item.daily_return for item in comparator if item.daily_return is not None
    }
    path_start = dynamic[0].session_date
    results: list[dict[str, object]] = []
    for window in windows:
        start = date.fromisoformat(window["start_inclusive"])
        end = date.fromisoformat(window["end_exclusive"])
        if start < path_start:
            results.append({"window_id": window["id"], "status": "NOT_APPLICABLE_PROFILE_START"})
            continue
        dates = sorted(day for day in dynamic_returns if start <= day < end)
        if not dates or any(day not in comparator_returns for day in dates):
            results.append({"window_id": window["id"], "status": "FAILED_DATE_ALIGNMENT"})
            continue
        dynamic_value = compound(dynamic_returns[day] for day in dates)
        comparator_value = compound(comparator_returns[day] for day in dates)
        results.append({
            "window_id": window["id"],
            "status": "PASS",
            "start_inclusive": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "paired_return_sessions": len(dates),
            "dynamic_total_return": str(dynamic_value),
            "comparator_total_return": str(comparator_value),
            "increment": str(dynamic_value - comparator_value),
        })
    return results


__all__ = [
    "BatchDailySnapshot", "BatchOrder", "FillAudit", "FormalPathEngine",
    "MarketSession", "PathPoint", "ProfilePITSelector", "ProfileSpec",
    "ProfileStrategy", "ScaledTransactionCostSchedule", "compound",
    "initial_path_point", "load_market_sessions", "load_session_dates", "path_metrics",
    "registered_profiles", "shifted_strategy_config", "snapshot_path_point",
    "window_effects",
]
