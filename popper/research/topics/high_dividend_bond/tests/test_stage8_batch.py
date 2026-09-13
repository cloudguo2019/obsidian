from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.stage8_batch import (  # noqa: E402
    BatchOrder,
    FormalPathEngine,
    MarketSession,
    ProfilePITSelector,
    ProfileStrategy,
    ScaledTransactionCostSchedule,
    initial_path_point,
    path_metrics,
    registered_profiles,
    shifted_strategy_config,
)
from engine.stage8_engine import (  # noqa: E402
    Account,
    DailyCloseLaggedEngine,
    DividendTaxRule,
    DividendTaxSchedule,
    FeeRule,
    HDAnchorStrategy,
    PITDividendRecord,
    PITDividendSelector,
    Session,
    TransactionCostSchedule,
    dec,
)


TZ = timezone(timedelta(hours=8))
TAX_VERSION = "PRC_LISTED_DIVIDEND_PIT_2015_101_PLUS_2012_85"


def fee_schedule() -> TransactionCostSchedule:
    start = date(2000, 1, 1)
    return TransactionCostSchedule([
        FeeRule("BROKER_COMMISSION", start, None, "BOTH", "transaction_amount", dec("0.0001"), dec("5")),
        FeeRule("STAMP_TAX", start, None, "SELL", "transaction_amount", dec("0.0005")),
        FeeRule("TRANSFER_FEE", start, None, "BOTH", "transaction_amount", dec("0.00001")),
        FeeRule("HANDLING_FEE", start, None, "BOTH", "transaction_amount", dec("0.0000341")),
        FeeRule("REGULATORY_FEE", start, None, "BOTH", "transaction_amount", dec("0.00002")),
    ])


def tax_schedule() -> DividendTaxSchedule:
    return DividendTaxSchedule([
        DividendTaxRule(TAX_VERSION, date(2015, 9, 8), None, "LE_1_CALENDAR_MONTH", dec("0.20"), "SUPPLEMENT_AT_SALE"),
        DividendTaxRule(TAX_VERSION, date(2015, 9, 8), None, "GT_1_CALENDAR_MONTH_LE_1_YEAR", dec("0.10"), "SUPPLEMENT_AT_SALE"),
        DividendTaxRule(TAX_VERSION, date(2015, 9, 8), None, "GT_1_YEAR", dec("0"), "NO_TAX_OVER_ONE_YEAR"),
    ])


def pit_record(start: date = date(2024, 1, 1), dps: str = "1") -> PITDividendRecord:
    available = datetime.combine(start, datetime.min.time(), tzinfo=TZ)
    return PITDividendRecord(
        "PIT", available, available, available + timedelta(days=365), None, dec(dps)
    )


def market(day: date, close: str, open_price: str | None = None, status: str = "TRADING") -> MarketSession:
    price = dec(close)
    return MarketSession(
        day,
        dec(open_price if open_price is not None else close) if status == "TRADING" else None,
        price if status == "TRADING" else None,
        status,
        price * dec("1.10") if status == "TRADING" else None,
        price * dec("0.90") if status == "TRADING" else None,
    )


def make_formal_engine(profile_id: str, *, price: str = "30") -> FormalPathEngine:
    profile = next(item for item in registered_profiles() if item.profile_id == profile_id)
    sessions = [date(2024, 1, 1) + timedelta(days=index) for index in range(20)]
    base_fees = fee_schedule()
    account = Account(
        "30000", 1000, price, date(2022, 1, 1), 0,
        ScaledTransactionCostSchedule(base_fees, profile.fee_multiplier), tax_schedule(),
    )
    selector = ProfilePITSelector(
        [pit_record()], session_dates=sessions,
        available_delay_sessions=profile.pit_available_delay_sessions,
        dividend_multiplier=profile.dividend_multiplier,
    )
    return FormalPathEngine(
        account=account,
        initial_mark=price,
        initial_date=date(2024, 1, 1),
        profile=profile,
        pit_selector=selector,
        strategy=ProfileStrategy(shifted_strategy_config(profile.yield_shift), profile.confirmation_bars),
        corporate_actions=(),
    )


class RegisteredProfileTests(unittest.TestCase):
    def test_profile_registry_is_complete_and_p21_fails_closed(self):
        profiles = registered_profiles()
        self.assertEqual([item.profile_id for item in profiles], [f"P{i:02d}" for i in range(24)])
        p21 = profiles[21]
        self.assertFalse(p21.runnable)
        self.assertEqual(p21.not_run_reason, "NO_AUDITABLE_EXECUTABLE_BROKER_CASH_RATE_INPUT")

    def test_registered_start_and_initial_inventory_overlays(self):
        profiles = {item.profile_id: item for item in registered_profiles()}
        self.assertEqual(profiles["P08"].start_date, date(2022, 6, 10))
        self.assertEqual(profiles["P09"].start_date, date(2022, 9, 13))
        self.assertEqual(profiles["P19"].dynamic_initial_shares, 1200)
        self.assertEqual(profiles["P20"].dynamic_initial_shares, 0)


class OverlayUnitTests(unittest.TestCase):
    def test_fee_multiplier_applies_after_normal_component_rounding(self):
        normal = fee_schedule().calculate(date(2024, 1, 2), "BUY", 100, dec("30"))
        doubled = ScaledTransactionCostSchedule(fee_schedule(), "2").calculate(
            date(2024, 1, 2), "BUY", 100, dec("30")
        )
        self.assertEqual(doubled.total, normal.total * 2)
        self.assertEqual(doubled.components["BROKER_COMMISSION"], dec("10"))

    def test_pit_delay_changes_only_available_time_and_multiplier_changes_only_dps(self):
        original = pit_record(date(2024, 1, 2), "1")
        sessions = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        selector = ProfilePITSelector(
            [original], session_dates=sessions, available_delay_sessions=1, dividend_multiplier="0.9"
        )
        self.assertIsNone(selector.select(datetime(2024, 1, 2, 15, tzinfo=TZ))[0])
        selected = selector.select(datetime(2024, 1, 3, 15, tzinfo=TZ))[0]
        self.assertEqual(selected.dps, dec("0.9"))
        self.assertEqual(selected.expiry_time, original.expiry_time)
        self.assertEqual(selected.effective_time, original.effective_time)

    def test_confirmation_one_two_three_and_yield_shift(self):
        one = ProfileStrategy(shifted_strategy_config(), 1)
        three = ProfileStrategy(shifted_strategy_config(), 3)
        common = dict(shares=1000, average_price=dec("30"), total_assets=dec("60000"), dividend_dps=dec("1"))
        self.assertEqual(one.decide(confirmation_closes=[dec("30")], **common).target_shares, 1100)
        self.assertEqual(three.decide(confirmation_closes=[dec("30"), dec("30"), dec("30")], **common).target_shares, 1100)
        self.assertEqual(three.decide(confirmation_closes=[dec("31"), dec("30"), dec("30")], **common).target_shares, 1000)
        lower = ProfileStrategy(shifted_strategy_config("-0.001"), 1)
        self.assertEqual(lower.config.buy_yields[1000], dec("0.032"))


class EngineOverlayTests(unittest.TestCase):
    def test_p00_matches_frozen_engine_for_signal_fill_and_nav(self):
        selector = PITDividendSelector([pit_record()])
        base_account = Account("30000", 1000, "30", date(2022, 1, 1), 0, fee_schedule(), tax_schedule())
        base = DailyCloseLaggedEngine(
            base_account, "30", date(2024, 1, 1), selector, HDAnchorStrategy(), ()
        )
        formal = make_formal_engine("P00")
        day1 = date(2024, 1, 2)
        day2 = date(2024, 1, 3)
        base_signal = base.step(Session(day1, dec("30"), "TRADING", dec("33"), dec("27")), 1)
        formal_signal = formal.step(market(day1, "30"), 1)
        self.assertEqual(base_signal.generated_order.target_shares, formal_signal.generated_order.target_shares)
        base_fill = base.step(Session(day2, dec("30"), "TRADING", dec("33"), dec("27")), 2)
        formal_fill = formal.step(market(day2, "30"), 2)
        self.assertEqual(base_fill.shares, formal_fill.shares)
        self.assertEqual(base_fill.nav, formal_fill.nav)
        self.assertEqual(formal_fill.reconciliation_difference, dec("0"))

    def test_delayed_profiles_fill_at_t_plus_2_and_t_plus_3(self):
        for profile_id, expected_index in (("P03", 3), ("P04", 4)):
            engine = make_formal_engine(profile_id)
            signal = engine.step(market(date(2024, 1, 2), "30"), 1)
            self.assertEqual(signal.generated_order.execute_session_index, expected_index)
            for index in range(2, expected_index):
                waiting = engine.step(market(date(2024, 1, index + 1), "30"), index)
                self.assertFalse(waiting.fills)
                self.assertEqual(waiting.signal_blocker, "ORDER_PENDING_HOLD")
            filled = engine.step(market(date(2024, 1, expected_index + 1), "30"), expected_index)
            self.assertEqual(filled.fills[0].status, "FILLED")
            self.assertEqual(filled.shares, 1100)

    def test_open_fill_and_adverse_close_fill_reconcile(self):
        open_engine = make_formal_engine("P05")
        open_engine.step(market(date(2024, 1, 2), "30"), 1)
        open_fill = open_engine.step(market(date(2024, 1, 3), "31", "29"), 2)
        self.assertEqual(open_fill.fills[0].fill_price, dec("29"))
        self.assertEqual(open_fill.execution_price_pnl, dec("200"))
        self.assertEqual(open_fill.reconciliation_difference, dec("0"))

        adverse = make_formal_engine("P06")
        adverse.step(market(date(2024, 1, 2), "30"), 1)
        adverse_fill = adverse.step(market(date(2024, 1, 3), "30"), 2)
        self.assertEqual(adverse_fill.fills[0].fill_price, dec("30.02"))
        self.assertEqual(adverse_fill.execution_price_pnl, dec("-2"))
        self.assertEqual(adverse_fill.reconciliation_difference, dec("0"))

    def test_every_tenth_fill_is_forced_unfilled_or_half_filled(self):
        for profile_id, expected_status, expected_shares in (
            ("P22", "UNFILLED", 1100),
            ("P23", "PARTIAL", 1050),
        ):
            engine = make_formal_engine(profile_id)
            last = None
            for index in range(1, 11):
                target = 1100 if index % 2 else 1000
                order = BatchOrder(
                    f"O{index}", date(2024, 1, index + 1), index - 1, index,
                    engine.account.shares, target, "ADJACENT_BUY" if target > engine.account.shares else "ADJACENT_SELL",
                    dec("30"), dec("1"),
                )
                last, _ = engine.execute_instruction(
                    order, market(date(2024, 1, index + 1), "30"), index, dec("30")
                )
            self.assertEqual(last.status, expected_status)
            self.assertEqual(engine.account.shares, expected_shares)

    def test_suspension_breaks_confirmation_chain(self):
        engine = make_formal_engine("P00")
        blocked = engine.step(market(date(2024, 1, 2), "30", status="SUSPENDED_OR_MISSING"), 1)
        self.assertEqual(blocked.signal_blocker, "NO_TRADABLE_COMPLETED_CLOSE")
        first = engine.step(market(date(2024, 1, 3), "30"), 2)
        self.assertEqual(first.signal_blocker, "CONFIRMATION_BAR_MISSING")
        second = engine.step(market(date(2024, 1, 4), "30"), 3)
        self.assertIsNotNone(second.generated_order)


class MetricsTests(unittest.TestCase):
    def test_path_metrics_detect_drawdown_recovery_and_frequency(self):
        account = Account("30000", 1000, "30", date(2022, 1, 1), 0, fee_schedule(), tax_schedule())
        first = initial_path_point(
            profile_id="P00", account_id="HD-ANCHOR-001",
            session=market(date(2024, 1, 1), "30"), account=account,
        )
        second = replace(
            first, session_date=date(2024, 1, 2), session_index=1,
            nav=dec("54000"), daily_return=dec("-0.1"), drawdown=dec("-0.1"),
        )
        third = replace(
            first, session_date=date(2024, 1, 3), session_index=2,
            nav=dec("60000"), daily_return=dec("0.1111111111111111111111111111"), drawdown=dec("0"),
        )
        metrics = path_metrics(
            [first, second, third], [], generated_order_count=0, pending_at_terminal=0,
            pit_valid_decision_sessions=2, pit_decision_sessions=2,
        )
        self.assertEqual(dec(metrics["max_drawdown"]), dec("-0.1"))
        self.assertEqual(metrics["longest_underwater_sessions"], 1)
        self.assertEqual(metrics["longest_underwater_calendar_days"], 1)
        self.assertEqual(metrics["longest_underwater_start_date"], "2024-01-02")
        self.assertEqual(metrics["longest_underwater_recovery_date"], "2024-01-03")
        self.assertEqual(metrics["recovery_gate"], "PASS")
        self.assertEqual(metrics["pit_coverage_ratio"], "1")


if __name__ == "__main__":
    unittest.main()
