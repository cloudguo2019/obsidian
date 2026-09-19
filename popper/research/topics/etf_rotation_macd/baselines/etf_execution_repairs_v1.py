"""Isolated L0 research implementation. No broker, SDK or file persistence.

Callers must supply complete account/order state, raw prices, an explicit fee
model and product-specific calendars. Fixtures do not establish real rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


def dec(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("non_finite_number")
    return result


ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class FeeModel:
    model_id: str
    buy_rate: Decimal
    minimum: Decimal

    def __post_init__(self):
        object.__setattr__(self, "buy_rate", dec(self.buy_rate))
        object.__setattr__(self, "minimum", dec(self.minimum))
        if not self.model_id or self.buy_rate < 0 or self.minimum < 0:
            raise ValueError("invalid_explicit_fee_model")

    def commission(self, gross: Decimal, *, reserve=False) -> Decimal:
        gross = dec(gross)
        if gross < 0:
            raise ValueError("negative_gross")
        if gross == 0:
            return ZERO
        return max(gross * self.buy_rate, self.minimum).quantize(
            CENT, rounding=ROUND_CEILING if reserve else ROUND_HALF_UP)


@dataclass(frozen=True)
class Position:
    symbol: str
    volume: int
    available: int
    market_value: Decimal

    def __post_init__(self):
        object.__setattr__(self, "market_value", dec(self.market_value))
        if not self.symbol or type(self.volume) is not int or type(self.available) is not int:
            raise ValueError("invalid_position")
        if not 0 <= self.available <= self.volume or self.market_value < 0:
            raise ValueError("invalid_position")
        if (self.volume == 0) != (self.market_value == 0):
            raise ValueError("missing_raw_position_valuation")


@dataclass(frozen=True)
class PendingBuy:
    """Only still-active/unresolved BUY remainders, including unknown submit.

    broker_frozen is the part of this reservation already excluded from the
    broker's available cash. SELL requests are never credited as proceeds.
    """
    order_id: str
    symbol: str
    remaining: int
    limit_price: Decimal
    broker_frozen: Decimal = ZERO

    def __post_init__(self):
        object.__setattr__(self, "limit_price", dec(self.limit_price))
        object.__setattr__(self, "broker_frozen", dec(self.broker_frozen))
        if not self.order_id or not self.symbol or type(self.remaining) is not int:
            raise ValueError("invalid_pending_buy")
        if self.remaining <= 0 or self.limit_price <= 0 or self.broker_frozen < 0:
            raise ValueError("invalid_pending_buy")


@dataclass(frozen=True)
class AccountSnapshot:
    equity: Decimal
    available_cash: Decimal
    positions: tuple[Position, ...]
    pending_buys: tuple[PendingBuy, ...] = ()
    complete: bool = False

    def __post_init__(self):
        object.__setattr__(self, "equity", dec(self.equity))
        object.__setattr__(self, "available_cash", dec(self.available_cash))
        object.__setattr__(self, "positions", tuple(self.positions))
        object.__setattr__(self, "pending_buys", tuple(self.pending_buys))
        if self.equity < 0 or self.available_cash < 0:
            raise ValueError("negative_account_balance")
        if len({p.symbol for p in self.positions}) != len(self.positions):
            raise ValueError("duplicate_position")
        if len({p.order_id for p in self.pending_buys}) != len(self.pending_buys):
            raise ValueError("duplicate_order")


@dataclass(frozen=True)
class Instrument:
    category: str
    group: str
    settlement: str  # T0 or T1, explicit rather than inferred from symbol
    calendar_id: str
    lot_size: int = 100

    def __post_init__(self):
        if not self.category or not self.group or not self.calendar_id:
            raise ValueError("missing_product_metadata")
        if self.settlement not in {"T0", "T1"} or type(self.lot_size) is not int or self.lot_size <= 0:
            raise ValueError("invalid_product_rule")


@dataclass(frozen=True)
class Limits:
    capital_cap: Decimal = Decimal("5000")
    max_symbols: int = 3
    symbol_pct: Decimal = Decimal("0.2")
    total_pct: Decimal = Decimal("0.6")

    def __post_init__(self):
        for name in ("capital_cap", "symbol_pct", "total_pct"):
            object.__setattr__(self, name, dec(getattr(self, name)))
        if self.capital_cap <= 0 or type(self.max_symbols) is not int or self.max_symbols <= 0:
            raise ValueError("invalid_limits")
        if not 0 < self.symbol_pct <= self.total_pct <= 1:
            raise ValueError("invalid_limits")


@dataclass(frozen=True)
class BuyPlan:
    allowed: bool
    reason: str
    target_volume: int = 0
    delta: int = 0
    fee_reserve: Decimal = ZERO
    cash_reserve: Decimal = ZERO
    projected_value: Decimal = ZERO
    capital_basis: Decimal = ZERO
    symbol_count: int = 0


class FullAccountGuard:
    def __init__(self, instruments: dict[str, Instrument], fees: FeeModel, limits=Limits()):
        self.instruments = dict(instruments)
        self.fees = fees
        self.limits = limits

    def plan_buy(self, snapshot: AccountSnapshot, symbol: str, limit_price,
                 *, target_pct=None, target_volume=None) -> BuyPlan:
        if not snapshot.complete:
            return BuyPlan(False, "incomplete_account_or_order_state")
        price = dec(limit_price)
        if price <= 0 or snapshot.equity <= 0:
            return BuyPlan(False, "invalid_price_or_equity")
        held = {p.symbol: p for p in snapshot.positions if p.volume > 0}
        live_symbols = set(held) | {p.symbol for p in snapshot.pending_buys} | {symbol}
        if not live_symbols <= self.instruments.keys():
            return BuyPlan(False, "missing_product_metadata")
        current = held[symbol].volume if symbol in held else 0
        if target_volume is None:
            if target_pct is None or not 0 <= dec(target_pct) <= 1:
                return BuyPlan(False, "missing_or_invalid_target")
            target_volume = int(min(snapshot.equity, self.limits.capital_cap) * dec(target_pct) / price)
        if type(target_volume) is not int or target_volume < 0:
            return BuyPlan(False, "invalid_target_volume")
        lot = self.instruments[symbol].lot_size
        # Round the BUY increment; do not accidentally trade odd shares held.
        already_ordered = sum(p.remaining for p in snapshot.pending_buys if p.symbol == symbol)
        max_lots = max(target_volume - current - already_ordered, 0) // lot
        categories = [self.instruments[s].category for s in live_symbols]
        groups = [self.instruments[s].group for s in live_symbols]
        if len(live_symbols) > self.limits.max_symbols:
            return BuyPlan(False, "max_symbols", target_volume=current, symbol_count=len(live_symbols))
        if len(set(categories)) != len(categories) or len(set(groups)) != len(groups):
            return BuyPlan(False, "category_or_group_limit", target_volume=current)
        pending_value = sum((p.limit_price * p.remaining for p in snapshot.pending_buys), ZERO)
        pending_fees = sum((self.fees.commission(p.limit_price * p.remaining, reserve=True)
                            for p in snapshot.pending_buys), ZERO)
        off_broker_cash = sum((max(p.limit_price * p.remaining +
                                  self.fees.commission(p.limit_price * p.remaining, reserve=True) -
                                  p.broker_frozen, ZERO) for p in snapshot.pending_buys), ZERO)
        cash = max(min(snapshot.available_cash, self.limits.capital_cap) - off_broker_cash, ZERO)
        # Stress the existing units of the current symbol at the BUY limit too.
        held_symbol_value = max(held[symbol].market_value, current * price) if symbol in held else ZERO
        held_value = sum((p.market_value for p in held.values()), ZERO)
        if symbol in held:
            held_value += held_symbol_value - held[symbol].market_value
        symbol_pending = sum((p.remaining * p.limit_price for p in snapshot.pending_buys if p.symbol == symbol), ZERO)

        def candidate(lots):
            delta = lots * lot
            gross = price * delta
            fee = self.fees.commission(gross, reserve=True)
            basis = min(self.limits.capital_cap, max(snapshot.equity - pending_fees - fee, ZERO))
            projected = held_value + pending_value + gross
            reason = "ok"
            if gross + fee > cash:
                reason = "cash_including_fees"
            elif projected > basis * self.limits.total_pct:
                reason = "total_exposure"
            elif held_symbol_value + symbol_pending + gross > basis * self.limits.symbol_pct:
                reason = "symbol_exposure"
            return BuyPlan(reason == "ok", reason, current + delta, delta, fee,
                           gross + fee, projected, basis, len(live_symbols))

        if max_lots == 0:
            return BuyPlan(False, "no_buy_lot", target_volume=current)
        first = candidate(1)
        if not first.allowed:
            return BuyPlan(False, first.reason, target_volume=current,
                           projected_value=first.projected_value, capital_basis=first.capital_basis,
                           symbol_count=first.symbol_count)
        low, high = 1, max_lots
        while low < high:
            middle = (low + high + 1) // 2
            if candidate(middle).allowed:
                low = middle
            else:
                high = middle - 1
        return candidate(low)


@dataclass(frozen=True)
class TradingCalendar:
    calendar_id: str
    valid_from: date
    valid_through: date
    sessions: frozenset[date]

    def __post_init__(self):
        object.__setattr__(self, "sessions", frozenset(self.sessions))
        if not self.calendar_id or self.valid_from > self.valid_through:
            raise ValueError("invalid_calendar")
        if any(d < self.valid_from or d > self.valid_through for d in self.sessions):
            raise ValueError("session_outside_calendar_coverage")

    def check_coverage(self, day: date):
        if not self.valid_from <= day <= self.valid_through:
            raise ValueError("calendar_coverage_missing")

    def is_session(self, day: date) -> bool:
        self.check_coverage(day)
        return day in self.sessions

    def next_session(self, day: date) -> date:
        if not self.is_session(day):
            raise ValueError("trade_on_non_session")
        future = [s for s in self.sessions if s > day]
        if not future:
            raise ValueError("next_session_coverage_missing")
        return min(future)


@dataclass
class LedgerPosition:
    volume: int = 0
    available: int = 0
    raw_price: Decimal = ZERO
    # Every purchase cohort retains its own release session.
    locks: list[tuple[date, int]] = field(default_factory=list)


@dataclass(frozen=True)
class TradeResult:
    accepted: bool
    reason: str
    commission: Decimal = ZERO


class ResearchLedger:
    """Cash/fee/settlement ledger for L0; not an executable broker adapter.

    FeeModel is applied to both sides in this ETF-only fixture; no tax model,
    distributions, interest or fill/slippage assumptions are supplied here.
    """
    def __init__(self, *, cash, day: date, instruments: dict[str, Instrument],
                 calendars: dict[str, TradingCalendar], fees: FeeModel,
                 positions: tuple[Position, ...] = (), raw_prices=None, balance_adjustment=0):
        self.cash = dec(cash)
        self.balance_adjustment = dec(balance_adjustment)
        self.day = day
        self.instruments = dict(instruments)
        self.calendars = dict(calendars)
        self.fees = fees
        self.positions: dict[str, LedgerPosition] = {}
        if self.cash < 0:
            raise ValueError("negative_cash")
        for p in positions:
            if p.symbol in self.positions:
                raise ValueError("duplicate_position")
            # Unknown existing locked cohorts cannot be guessed from quantity.
            if p.available != p.volume:
                raise ValueError("initial_locked_cohorts_required")
            price = dec((raw_prices or {})[p.symbol])
            if price <= 0 or price * p.volume != p.market_value:
                raise ValueError("inconsistent_initial_raw_valuation")
            self.positions[p.symbol] = LedgerPosition(p.volume, p.available, price)
            self._calendar(p.symbol).check_coverage(day)

    def _calendar(self, symbol):
        rule = self.instruments.get(symbol)
        if rule is None:
            raise ValueError("missing_product_rule")
        calendar = self.calendars.get(rule.calendar_id)
        if calendar is None or calendar.calendar_id != rule.calendar_id:
            raise ValueError("missing_applicable_calendar")
        return calendar

    def advance_to(self, day: date):
        if day < self.day:
            raise ValueError("backward_ledger_date")
        # Validate all coverage before changing any cash/position/date state.
        for symbol in self.positions:
            self._calendar(symbol).check_coverage(day)
        for symbol, p in self.positions.items():
            matured = [(release, qty) for release, qty in p.locks if release <= day]
            p.available += sum(qty for release, qty in matured)
            p.locks = [(release, qty) for release, qty in p.locks if release > day]
        self.day = day

    def mark(self, symbol, raw_price):
        price = dec(raw_price)
        if price <= 0:
            raise ValueError("invalid_raw_price")
        self.positions[symbol].raw_price = price

    def snapshot(self, pending_buys=()) -> AccountSnapshot:
        positions = tuple(Position(s, p.volume, p.available, p.volume * p.raw_price)
                          for s, p in sorted(self.positions.items()) if p.volume > 0)
        equity = self.cash + sum((p.market_value for p in positions), ZERO) + self.balance_adjustment
        return AccountSnapshot(equity, self.cash, positions, tuple(pending_buys), complete=True)

    def execute(self, symbol, side, volume: int, raw_price) -> TradeResult:
        try:
            price = dec(raw_price)
            rule = self.instruments.get(symbol)
            calendar = self._calendar(symbol)
            if not calendar.is_session(self.day):
                raise ValueError("trade_on_non_session")
            if type(volume) is not int or volume <= 0 or price <= 0 or side not in {"BUY", "SELL"}:
                raise ValueError("invalid_trade")
            position = self.positions.get(symbol, LedgerPosition())
            release = None
            if side == "BUY":
                if volume % rule.lot_size:
                    raise ValueError("invalid_buy_lot")
                if rule.settlement == "T1":
                    release = calendar.next_session(self.day)
            elif volume > position.available:
                raise ValueError("no_sellable_volume")
            elif volume % rule.lot_size and volume != position.volume:
                raise ValueError("odd_lot_requires_full_exit")
            gross = price * volume
            fee = self.fees.commission(gross)
            if side == "BUY" and gross + fee > self.cash:
                raise ValueError("cash_including_fees")
            if side == "SELL" and self.cash + gross < fee:
                raise ValueError("cash_including_fees")
        except (ValueError, KeyError) as exc:
            return TradeResult(False, str(exc))
        # Commit only after validation so rejection cannot partially mutate.
        position.raw_price = price
        if side == "BUY":
            self.cash -= gross + fee
            position.volume += volume
            if release is None:
                position.available += volume
            else:
                position.locks.append((release, volume))
        else:
            self.cash += gross - fee
            position.volume -= volume
            position.available -= volume
        self.positions[symbol] = position
        return TradeResult(True, "ok", fee)
