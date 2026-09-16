from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "baselines"))
from etf_price_contract_v1 import ProxyTick, RatioEvent, RawDailyClose, build_price_snapshot


TZ = timezone(timedelta(hours=8))
DAY = date(2026, 9, 16)
DECISION = datetime(2026, 9, 16, 14, 57, 5, tzinfo=TZ)


def daily(day: int, price: float, **kwargs) -> RawDailyClose:
    return RawDailyClose(
        date(2026, 9, day), price, datetime(2026, 9, day, 16, tzinfo=TZ), **kwargs
    )


def tick(price: float = 0.96) -> ProxyTick:
    return ProxyTick(price, DECISION - timedelta(seconds=1), DECISION)


def event(day: int, multiplier: float, event_id: str = "event-1") -> RatioEvent:
    return RatioEvent(
        event_id,
        datetime(2026, 9, day, 9, tzinfo=TZ),
        datetime(2026, 9, day - 1, 18, tzinfo=TZ),
        multiplier,
    )


def snapshot(bars=None, quote=None, events=(), **kwargs):
    return build_price_snapshot(
        bars if bars is not None else [daily(15, 1.0)],
        quote if quote is not None else tick(),
        events,
        decision_at=DECISION,
        factor_manifest_id="synthetic-factors/v1",
        events_complete_as_of=kwargs.pop("events_complete_as_of", True),
        **kwargs,
    )


class PriceContractTests(unittest.TestCase):
    def test_no_event_keeps_raw_tick_and_history(self):
        result = snapshot()
        self.assertEqual(result.signal_closes, (1.0, 0.96))
        self.assertEqual(result.raw_proxy_price, 0.96)
        self.assertEqual((result.signal_adjust, result.raw_adjust), ("front_ratio", "none"))

    def test_ex_dividend_reanchors_history_not_today_tick(self):
        result = snapshot(events=[event(16, 0.95)])
        self.assertEqual(result.signal_closes, (0.95, 0.96))
        self.assertEqual(result.raw_proxy_price, 0.96)
        self.assertEqual(result.applied_event_ids, ("event-1",))

    def test_multiple_events_compound_only_before_each_effective_day(self):
        result = snapshot(
            bars=[daily(15, 1.0), daily(14, 1.0), daily(13, 1.0)],
            events=[event(16, 0.95, "second"), event(14, 0.9, "first")],
        )
        for actual, expected in zip(result.signal_closes, (0.855, 0.95, 0.95, 0.96)):
            self.assertAlmostEqual(actual, expected)

    def test_known_future_event_is_not_applied(self):
        result = snapshot(events=[event(17, 0.5, "future")])
        self.assertEqual(result.signal_closes, (1.0, 0.96))
        self.assertEqual(result.applied_event_ids, ())

    def test_today_and_future_daily_bars_are_removed(self):
        result = snapshot(bars=[daily(15, 1.0), daily(16, 999.0), daily(17, 9999.0)])
        self.assertEqual(result.trading_dates, (date(2026, 9, 15), DAY))
        self.assertEqual(result.signal_closes, (1.0, 0.96))

    def test_adjusted_cache_is_rejected_instead_of_double_adjusted(self):
        with self.assertRaisesRegex(ValueError, "raw 1d/none"):
            snapshot(bars=[daily(15, 0.95, adjust="front_ratio")])

    def test_late_received_tick_cannot_enter_earlier_decision(self):
        late = ProxyTick(0.96, DECISION - timedelta(seconds=1), DECISION + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "not available"):
            snapshot(quote=late)

    def test_stale_or_future_quote_is_rejected(self):
        quotes = [
            ProxyTick(0.96, DECISION - timedelta(seconds=31), DECISION),
            ProxyTick(0.96, DECISION + timedelta(seconds=1), DECISION),
        ]
        for quote in quotes:
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                snapshot(quote=quote)

    def test_effective_but_late_known_event_fails_closed(self):
        late = RatioEvent("late", DECISION - timedelta(hours=5), DECISION + timedelta(seconds=1), 0.95)
        with self.assertRaisesRegex(ValueError, "as-of information"):
            snapshot(events=[late])

    def test_incomplete_manifest_duplicate_dates_and_events_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete versioned"):
            snapshot(events_complete_as_of=False)
        with self.assertRaisesRegex(ValueError, "duplicate historical"):
            snapshot(bars=[daily(15, 1.0), daily(15, 1.1)])
        with self.assertRaisesRegex(ValueError, "identifiers"):
            snapshot(events=[event(16, 0.95), event(16, 0.95)])

    def test_invalid_prices_multipliers_and_naive_times_are_rejected(self):
        for price in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(price=price), self.assertRaises(ValueError):
                snapshot(quote=tick(price))
        with self.assertRaises(ValueError):
            snapshot(events=[event(16, 0.0)])
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            snapshot(quote=ProxyTick(0.96, DECISION.replace(tzinfo=None), DECISION))

    def test_historical_close_must_have_been_available(self):
        unavailable = RawDailyClose(date(2026, 9, 15), 1.0, DECISION + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "historical close was not available"):
            snapshot(bars=[unavailable])


if __name__ == "__main__":
    unittest.main(verbosity=2)
