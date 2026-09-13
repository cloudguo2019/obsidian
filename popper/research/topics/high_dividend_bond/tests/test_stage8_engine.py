from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.stage8_engine import (  # noqa: E402
    Account,
    CorporateAction,
    DataGateError,
    DailyCloseLaggedEngine,
    DividendTaxRule,
    DividendTaxSchedule,
    FeeRule,
    HDAnchorStrategy,
    OrderInstruction,
    PITDividendRecord,
    PITDividendSelector,
    Session,
    TransactionCostSchedule,
    dec,
    initialize_research_account,
)


TZ = timezone(timedelta(hours=8))
CURRENT_TAX = "PRC_LISTED_DIVIDEND_PIT_2015_101_PLUS_2012_85"
OLD_TAX = "PRC_LISTED_DIVIDEND_PIT_2012_85"


def fee_schedule() -> TransactionCostSchedule:
    start = date(2000, 1, 1)
    return TransactionCostSchedule(
        [
            FeeRule("BROKER_COMMISSION", start, None, "BOTH", "transaction_amount", dec("0.0001"), dec("5")),
            FeeRule("STAMP_TAX", start, None, "SELL", "transaction_amount", dec("0.0005")),
            FeeRule("TRANSFER_FEE", start, None, "BOTH", "transaction_amount", dec("0.00001")),
            FeeRule("HANDLING_FEE", start, None, "BOTH", "transaction_amount", dec("0.0000341")),
            FeeRule("REGULATORY_FEE", start, None, "BOTH", "transaction_amount", dec("0.00002")),
        ]
    )


def tax_schedule() -> DividendTaxSchedule:
    current_start = date(2015, 9, 8)
    old_start = date(2013, 1, 1)
    old_end = date(2015, 9, 7)
    rows = [
        DividendTaxRule(CURRENT_TAX, current_start, None, "LE_1_CALENDAR_MONTH", dec("0.20"), "SUPPLEMENT_AT_SALE"),
        DividendTaxRule(CURRENT_TAX, current_start, None, "GT_1_CALENDAR_MONTH_LE_1_YEAR", dec("0.10"), "SUPPLEMENT_AT_SALE"),
        DividendTaxRule(CURRENT_TAX, current_start, None, "GT_1_YEAR", dec("0"), "NO_TAX_OVER_ONE_YEAR"),
        DividendTaxRule(OLD_TAX, old_start, old_end, "LE_1_CALENDAR_MONTH", dec("0.20"), "FINAL_BY_HOLDING_PERIOD", dec("0.05")),
        DividendTaxRule(OLD_TAX, old_start, old_end, "GT_1_CALENDAR_MONTH_LE_1_YEAR", dec("0.10"), "FINAL_BY_HOLDING_PERIOD", dec("0.05")),
        DividendTaxRule(OLD_TAX, old_start, old_end, "GT_1_YEAR", dec("0.05"), "FINAL_BY_HOLDING_PERIOD", dec("0.05")),
    ]
    return DividendTaxSchedule(rows)


def pit_selector(dps: str = "1", start: date = date(2024, 1, 1)) -> PITDividendSelector:
    available = datetime.combine(start, datetime.min.time(), tzinfo=TZ)
    return PITDividendSelector(
        [
            PITDividendRecord(
                record_id="PIT-1",
                available_time=available,
                effective_time=available,
                expiry_time=available + timedelta(days=365),
                superseded_time=None,
                dps=dec(dps),
            )
        ]
    )


def session(day: date, close: str, status: str = "TRADING") -> Session:
    price = dec(close)
    return Session(day, price if status == "TRADING" else None, status, price * dec("1.10"), price * dec("0.90"))


class StrategyStateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = HDAnchorStrategy()

    def decide(self, shares: int, previous: str, current: str, gate: str = "NORMAL", avg: str = "20", nav: str = "60000"):
        return self.strategy.decide(
            shares=shares,
            average_price=dec(avg),
            total_assets=dec(nav),
            previous_close=dec(previous),
            current_close=dec(current),
            dividend_dps=dec("1"),
            fundamental_gate=gate,
        )

    def test_adjacent_hysteresis_and_inclusive_boundaries(self):
        self.assertEqual(self.decide(1000, "30.3030303030", "30.3030303030").target_shares, 1100)
        self.assertEqual(self.decide(1100, "31", "31").target_shares, 1100)
        self.assertEqual(self.decide(1200, "30.3030303031", "30.3030303031").target_shares, 1100)

    def test_deep_value_walk_stops_at_1400(self):
        state = 1000
        for expected in (1100, 1200, 1300, 1400):
            state = self.decide(state, "23", "23").target_shares
            self.assertEqual(state, expected)
        self.assertEqual(self.decide(1400, "23", "23").target_shares, 1400)

    def test_core_build_illegal_state_and_excess_correction(self):
        self.assertEqual(self.decide(0, "40", "40").target_shares, 100)
        self.assertEqual(self.decide(900, "40", "40").target_shares, 1000)
        self.assertEqual(self.decide(1150, "20", "20").reason, "ILLEGAL_DISCRETE_STATE_HOLD")
        self.assertEqual(self.decide(1600, "20", "20").target_shares, 1500)

    def test_fundamental_gates(self):
        self.assertEqual(self.decide(1200, "31", "31", "REVIEW").target_shares, 1200)
        self.assertEqual(self.decide(1000, "20", "20", "STOP_ADD").target_shares, 1000)
        self.assertEqual(self.decide(1200, "31", "31", "STOP_ADD").target_shares, 1100)
        self.assertEqual(self.decide(1400, "20", "20", "EXIT").target_shares, 0)

    def test_loss_impact_stops_only_adds(self):
        blocked = self.decide(1000, "20", "20", avg="30", nav="60000")
        self.assertEqual(blocked.reason, "ACCOUNT_LOSS_STOP_ADD")
        selling = self.decide(1200, "31", "31", avg="50", nav="60000")
        self.assertEqual(selling.target_shares, 1100)


class PITTests(unittest.TestCase):
    def test_inclusive_expiry_and_exclusive_supersession(self):
        start = datetime(2024, 1, 2, 9, 30, tzinfo=TZ)
        old = PITDividendRecord("OLD", start, start, start + timedelta(days=365),
                                datetime(2024, 6, 3, 9, 30, tzinfo=TZ), dec("0.8"))
        new_time = datetime(2024, 6, 3, 9, 30, tzinfo=TZ)
        new = PITDividendRecord("NEW", new_time, new_time, new_time + timedelta(days=365), None, dec("1"))
        selector = PITDividendSelector([old, new])
        chosen, _ = selector.select(datetime(2025, 6, 3, 9, 30, tzinfo=TZ))
        self.assertEqual(chosen.record_id, "NEW")
        chosen, _ = selector.select(datetime(2025, 6, 4, 9, 30, tzinfo=TZ))
        self.assertIsNone(chosen)

    def test_future_method_mismatch_and_zero_are_blocked(self):
        now = datetime(2024, 1, 2, 15, 0, tzinfo=TZ)
        wrong = PITDividendRecord("WRONG", now, now, now + timedelta(days=365), None, dec("1"), "WRONG")
        chosen, reason = PITDividendSelector([wrong]).select(now)
        self.assertIsNone(chosen)
        self.assertEqual(reason, "NO_VALID_PIT_DIVIDEND")
        zero = PITDividendRecord("ZERO", now, now, now + timedelta(days=365), None, dec("0"))
        chosen, reason = PITDividendSelector([zero]).select(now)
        self.assertIsNone(chosen)
        self.assertEqual(reason, "ZERO_DIVIDEND_BLOCK")


class FeeAndInventoryTests(unittest.TestCase):
    def test_2024_fee_components(self):
        buy = fee_schedule().calculate(date(2024, 1, 2), "BUY", 100, dec("10"))
        sell = fee_schedule().calculate(date(2024, 1, 2), "SELL", 100, dec("10"))
        self.assertEqual(buy.total, dec("5.06"))
        self.assertEqual(sell.total, dec("5.56"))
        self.assertEqual(sell.components["BROKER_COMMISSION"], dec("5.00"))

    def test_t1_inventory_is_explicit(self):
        account = Account("5000", 0, "10", date(2024, 1, 1), 0, fee_schedule(), tax_schedule())
        buy = OrderInstruction("B", date(2024, 1, 2), 1, 0, 100, "TEST")
        self.assertEqual(account.execute(buy, session(date(2024, 1, 2), "10"), 1).status, "FILLED")
        sell = OrderInstruction("S", date(2024, 1, 2), 1, 100, 0, "TEST")
        same_day = account.execute(sell, session(date(2024, 1, 2), "10"), 1)
        self.assertEqual(same_day.reason, "INSUFFICIENT_T1_INVENTORY")
        self.assertEqual(account.execute(sell, session(date(2024, 1, 3), "10"), 2).status, "FILLED")

    def test_insufficient_cash_and_missing_limit_fail_closed(self):
        account = Account("1000", 0, "10", date(2024, 1, 1), 0, fee_schedule(), tax_schedule())
        order = OrderInstruction("B", date(2024, 1, 2), 1, 0, 100, "TEST")
        result = account.execute(order, session(date(2024, 1, 2), "10"), 1)
        self.assertEqual(result.reason, "INSUFFICIENT_CASH")
        no_limit = Session(date(2024, 1, 3), dec("10"), "TRADING", None, dec("9"))
        result = account.execute(order, no_limit, 2)
        self.assertEqual(result.reason, "MISSING_BUY_PROTECTION_LIMIT")

    def test_missing_dated_fee_rule_is_not_silently_zero(self):
        incomplete = TransactionCostSchedule(
            [FeeRule("BROKER_COMMISSION", date(2024, 1, 1), None, "BOTH", "transaction_amount", dec("0.0001"), dec("5")),
             FeeRule("STAMP_TAX", date(2025, 1, 1), None, "SELL", "transaction_amount", dec("0.0005"))]
        )
        with self.assertRaisesRegex(DataGateError, "missing STAMP_TAX"):
            incomplete.calculate(date(2024, 1, 2), "BUY", 100, dec("10"))


class DividendLedgerTests(unittest.TestCase):
    def make_account(self, acquired: date, shares: int = 100) -> Account:
        return Account("59000", shares, "10", acquired, 0, fee_schedule(), tax_schedule())

    def test_record_ex_pay_are_separate_and_long_holding_is_tax_free(self):
        account = self.make_account(date(2022, 1, 1))
        action = CorporateAction("DIV", date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5), dec("1"), CURRENT_TAX)
        account.snapshot_record_date(action)
        self.assertEqual(account.dividend_receivable, dec("0"))
        self.assertEqual(account.recognize_dividend(action), dec("100"))
        self.assertEqual(account.dividend_receivable, dec("100"))
        self.assertEqual(account.revalue_tax_liability(date(2024, 1, 3)), dec("0"))
        before = account.cash
        gross, withheld = account.pay_dividend(action, date(2024, 1, 5))
        self.assertEqual((gross, withheld), (dec("100"), dec("0")))
        self.assertEqual(account.cash - before, dec("100"))
        self.assertEqual(account.dividend_receivable, dec("0"))

    def test_current_deferred_tax_is_reserved_and_settled_on_sale(self):
        account = self.make_account(date(2024, 1, 1))
        action = CorporateAction("DIV", date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 3), dec("1"), CURRENT_TAX)
        account.snapshot_record_date(action)
        account.recognize_dividend(action)
        self.assertEqual(account.revalue_tax_liability(date(2024, 1, 3)), dec("20"))
        account.pay_dividend(action, date(2024, 1, 3))
        self.assertEqual(account.tax_liability, dec("20"))
        account.revalue_tax_liability(date(2024, 2, 2))
        self.assertEqual(account.tax_liability, dec("10"))
        order = OrderInstruction("S", date(2024, 2, 2), 2, 100, 0, "TEST")
        fill = account.execute(order, session(date(2024, 2, 2), "10"), 2)
        self.assertEqual(fill.deferred_tax_paid, dec("10"))
        self.assertEqual(account.tax_liability, dec("0"))

    def test_old_regime_initial_withholding_and_supplement(self):
        account = self.make_account(date(2014, 1, 1))
        action = CorporateAction("OLD", date(2014, 1, 2), date(2014, 1, 3), date(2014, 1, 3), dec("1"), OLD_TAX)
        account.snapshot_record_date(action)
        account.recognize_dividend(action)
        account.revalue_tax_liability(date(2014, 1, 3))
        self.assertEqual(account.tax_liability, dec("20"))
        gross, withheld = account.pay_dividend(action, date(2014, 1, 3))
        self.assertEqual((gross, withheld), (dec("100"), dec("5")))
        self.assertEqual(account.tax_liability, dec("15"))
        # The entitlement keeps its frozen 2013--2015 policy version even when
        # its eventual holding-period measurement occurs after that era.
        account.revalue_tax_liability(date(2016, 1, 4))
        self.assertEqual(account.tax_liability, dec("0"))


class EngineIntegrationTests(unittest.TestCase):
    def make_engine(self, shares: int = 1000, price: str = "31", cash: str | None = None,
                    actions=(), selector: PITDividendSelector | None = None, strategy=True):
        if cash is None:
            cash = str(dec("60000") - dec(shares) * dec(price))
        account = Account(cash, shares, price, date(2022, 1, 1), 0, fee_schedule(), tax_schedule())
        return DailyCloseLaggedEngine(
            account,
            price,
            date(2024, 1, 1),
            pit_selector=selector or pit_selector(),
            strategy=HDAnchorStrategy() if strategy else None,
            corporate_actions=actions,
        )

    def test_signal_uses_t_close_and_fills_only_at_t_plus_1_close(self):
        engine = self.make_engine(shares=1200, price="31")
        t = engine.step(session(date(2024, 1, 2), "31"), 1)
        self.assertEqual(t.shares, 1200)
        self.assertEqual(t.generated_order.target_shares, 1100)
        t1 = engine.step(session(date(2024, 1, 3), "30"), 2)
        self.assertEqual(t1.shares, 1100)
        self.assertEqual(t1.fills[0].price, dec("30"))
        self.assertEqual(t1.fills[0].session_date, date(2024, 1, 3))

    def test_unfilled_order_is_cancelled_not_carried(self):
        engine = self.make_engine(shares=1200, price="31")
        engine.step(session(date(2024, 1, 2), "31"), 1)
        suspended = engine.step(session(date(2024, 1, 3), "31", "SUSPENDED_OR_MISSING"), 2)
        self.assertEqual(suspended.fills[0].reason, "NOT_TRADABLE")
        self.assertEqual(suspended.shares, 1200)
        resumed = engine.step(session(date(2024, 1, 4), "31"), 3)
        self.assertEqual(resumed.fills, ())
        self.assertEqual(resumed.signal_blocker, "CONFIRMATION_BAR_MISSING")

    def test_fill_on_record_date_controls_entitlement(self):
        action = CorporateAction("DIV", date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 4), dec("1"), CURRENT_TAX)
        engine = self.make_engine(shares=1200, price="31", actions=[action])
        engine.step(session(date(2024, 1, 2), "31"), 1)
        record = engine.step(session(date(2024, 1, 3), "31"), 2)
        self.assertEqual(record.shares, 1100)
        ex = engine.step(session(date(2024, 1, 4), "31"), 3)
        self.assertEqual(ex.new_dividend_entitlement, dec("1100"))

    def test_daily_accounting_reconciles_price_dividend_tax_and_fees(self):
        action = CorporateAction("DIV", date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 3), dec("1"), CURRENT_TAX)
        engine = self.make_engine(shares=1200, price="31", actions=[action])
        record = engine.step(session(date(2024, 1, 2), "31"), 1)
        self.assertEqual(record.reconciliation_difference, dec("0"))
        ex_and_fill = engine.step(session(date(2024, 1, 3), "30"), 2)
        self.assertEqual(ex_and_fill.new_dividend_entitlement, dec("1200"))
        self.assertEqual(ex_and_fill.transaction_fees, dec("6.69"))
        self.assertEqual(ex_and_fill.reconciliation_difference, dec("0"))

    def test_daily_reconciliation_handles_tax_reserve_remeasurement_and_settlement(self):
        action = CorporateAction("DIV", date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 3), dec("1"), CURRENT_TAX)
        account = Account("59000", 100, "10", date(2024, 1, 1), 0, fee_schedule(), tax_schedule())
        engine = DailyCloseLaggedEngine(account, "10", date(2024, 1, 1), strategy=None, corporate_actions=[action])
        engine.step(session(date(2024, 1, 2), "10"), 1)
        ex_pay = engine.step(session(date(2024, 1, 3), "10"), 2)
        self.assertEqual(ex_pay.new_dividend_entitlement, dec("100"))
        self.assertEqual(ex_pay.tax_reserve_change, dec("20"))
        self.assertEqual(ex_pay.actual_nav_change, dec("80"))
        self.assertEqual(ex_pay.reconciliation_difference, dec("0"))
        one_month_passed = engine.step(session(date(2024, 2, 2), "10"), 3)
        self.assertEqual(one_month_passed.tax_reserve_change, dec("-10"))
        self.assertEqual(one_month_passed.actual_nav_change, dec("10"))
        self.assertEqual(one_month_passed.reconciliation_difference, dec("0"))
        sell = OrderInstruction("S", date(2024, 2, 2), 4, 100, 0, "TEST")
        engine.pending[4] = [sell]
        sold = engine.step(session(date(2024, 2, 5), "10"), 4)
        self.assertEqual(sold.fills[0].deferred_tax_paid, dec("10"))
        self.assertEqual(sold.reconciliation_difference, dec("0"))

    def test_static_baseline_initialization_has_no_fictitious_order_or_fee(self):
        account = initialize_research_account(
            common_assets="60000",
            shares=1000,
            price_ref="22.71",
            t0=date(2022, 3, 10),
            initial_session_index=0,
            fee_schedule=fee_schedule(),
            tax_schedule=tax_schedule(),
        )
        self.assertEqual(account.cash, dec("37290"))
        self.assertEqual(account.nav(dec("22.71")), dec("60000"))
        engine = DailyCloseLaggedEngine(account, "22.71", date(2022, 3, 10), strategy=None)
        snap = engine.step(session(date(2022, 3, 11), "22.71"), 1)
        self.assertEqual(snap.fills, ())
        self.assertEqual(snap.transaction_fees, dec("0"))
        self.assertEqual(snap.nav, dec("60000"))


if __name__ == "__main__":
    unittest.main()
