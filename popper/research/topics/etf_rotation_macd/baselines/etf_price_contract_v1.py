"""Research-only, point-in-time ratio-adjusted proxy-close construction.

No SDK calls, brokerage access, fills, or account mutation. Event multipliers
must be supplied by a separately validated provider adapter, not inferred from
an arbitrary SDK factor column. Only close is synthesized, not an OHLC bar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence


CONTRACT_ID = "ETF-PRICE-001/v1.0"


@dataclass(frozen=True)
class RawDailyClose:
    trading_date: date
    close: float
    available_at: datetime
    period: str = "1d"
    adjust: str = "none"


@dataclass(frozen=True)
class RatioEvent:
    event_id: str
    effective_at: datetime
    available_at: datetime
    backward_multiplier: float


@dataclass(frozen=True)
class ProxyTick:
    price: float
    quote_at: datetime
    received_at: datetime
    adjust: str = "none"


@dataclass(frozen=True)
class PriceSnapshot:
    decision_at: datetime
    trading_dates: tuple[date, ...]
    signal_closes: tuple[float, ...]
    raw_proxy_price: float
    applied_event_ids: tuple[str, ...]
    factor_manifest_id: str
    contract_id: str = CONTRACT_ID
    signal_adjust: str = "front_ratio"
    raw_adjust: str = "none"


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return result


def build_price_snapshot(
    daily_closes: Sequence[RawDailyClose],
    tick: ProxyTick,
    events: Sequence[RatioEvent],
    *,
    decision_at: datetime,
    factor_manifest_id: str,
    events_complete_as_of: bool,
    max_quote_age: timedelta = timedelta(seconds=30),
) -> PriceSnapshot:
    """Anchor at decision day; each event rescales only earlier daily closes.

    An event's backward_multiplier is explicitly defined as the factor applied
    to prices before its effective trading date (e.g. 0.95 in a synthetic cash
    ex-dividend example). The caller supplies a complete as-of event manifest.
    Time comparisons use aware timestamps; day boundaries use decision timezone.
    """

    _aware(decision_at, "decision_at")
    if not factor_manifest_id.strip() or events_complete_as_of is not True:
        raise ValueError("complete versioned as-of factor manifest is required")
    if max_quote_age < timedelta(0):
        raise ValueError("max_quote_age must be nonnegative")
    if tick.adjust != "none":
        raise ValueError("tick must be an unadjusted actual-price quote")
    _aware(tick.quote_at, "tick.quote_at")
    _aware(tick.received_at, "tick.received_at")
    if tick.quote_at > tick.received_at or tick.received_at > decision_at:
        raise ValueError("tick was not available at the decision cutoff")
    if decision_at - tick.quote_at > max_quote_age:
        raise ValueError("tick quote is stale")
    raw_proxy = _positive(tick.price, "tick.price")
    anchor_day = decision_at.date()

    active_events: list[RatioEvent] = []
    event_ids: set[str] = set()
    for event in events:
        _aware(event.effective_at, "event.effective_at")
        _aware(event.available_at, "event.available_at")
        if event.effective_at > decision_at:
            continue  # A known future distribution is not effective yet.
        if event.available_at > decision_at:
            raise ValueError("effective event is missing from the as-of information set")
        if not event.event_id.strip() or event.event_id in event_ids:
            raise ValueError("effective event identifiers must be nonempty and unique")
        _positive(event.backward_multiplier, "event.backward_multiplier")
        event_ids.add(event.event_id)
        active_events.append(event)
    active_events.sort(key=lambda event: (event.effective_at, event.event_id))

    historical: dict[date, RawDailyClose] = {}
    for bar in daily_closes:
        if bar.adjust != "none" or bar.period != "1d":
            raise ValueError("daily input must be raw 1d/none, not adjusted cache")
        if bar.trading_date >= anchor_day:
            continue  # Discard today's incomplete/complete daily bar and future bars.
        _aware(bar.available_at, "bar.available_at")
        if bar.available_at > decision_at:
            raise ValueError("historical close was not available at the decision cutoff")
        if bar.trading_date in historical:
            raise ValueError("duplicate historical trading date")
        _positive(bar.close, "bar.close")
        historical[bar.trading_date] = bar
    if not historical:
        raise ValueError("historical daily closes are required")

    dates = sorted(historical)
    adjusted: list[float] = []
    for trading_day in dates:
        price = float(historical[trading_day].close)
        for event in active_events:
            effective_day = event.effective_at.astimezone(decision_at.tzinfo).date()
            if trading_day < effective_day:
                price *= float(event.backward_multiplier)
        adjusted.append(_positive(price, "adjusted close"))

    # Today's factor / today's anchor factor = 1. Preserve raw quote separately
    # so signal prices never need to be reused as brokerage sizing/fill inputs.
    return PriceSnapshot(
        decision_at=decision_at,
        trading_dates=tuple(dates + [anchor_day]),
        signal_closes=tuple(adjusted + [raw_proxy]),
        raw_proxy_price=raw_proxy,
        applied_event_ids=tuple(event.event_id for event in active_events),
        factor_manifest_id=factor_manifest_id,
    )
