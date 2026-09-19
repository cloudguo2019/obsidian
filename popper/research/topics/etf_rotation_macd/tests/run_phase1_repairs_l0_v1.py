"""Three authorized repairs: real legacy pipeline + isolated guard/ledger.

All account states, rates, product rules and calendars are SYNTHETIC fixtures.
No SDK, live broker, formal backtest, simulation process or real order is used.
Old diagnostic sources/results stay immutable, including two clock failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
TOPIC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOPIC / "baselines"))
from etf_execution_repairs_v1 import (
    AccountSnapshot, FeeModel, FullAccountGuard, Instrument, Limits, PendingBuy,
    Position, ResearchLedger, TradingCalendar, dec,
)
# This import loads the indexed engine but does not run its original tests.
import run_phase1_execution_l0_v1 as old
from etf_execution_bridge_v1 import ResearchRiskManager
from sartre_core.engine.context import SymbolPosition

A, B, C, D = old.A, old.B, old.C, old.D
FEES = FeeModel("SYNTHETIC-shadow-rate-0.0001-min-0.10", dec("0.0001"), dec("0.1"))
FRI, SAT, MON, TUE, WED = [date(2026, 9, d) for d in (11, 12, 14, 15, 16)]
# Artificially different product sessions: not assertions about SH/SZ holidays.
CAL_SH = TradingCalendar("SYNTHETIC-SH", date(2026, 9, 9), date(2026, 9, 20),
    frozenset(date(2026, 9, d) for d in (9, 10, 11, 14, 15, 16, 17, 18)))
CAL_SZ = TradingCalendar("SYNTHETIC-SZ-Monday-closed", date(2026, 9, 9), date(2026, 9, 20),
    frozenset(date(2026, 9, d) for d in (9, 10, 11, 15, 16, 17, 18)))
RULES = {
    A: Instrument("cat-A", "group-A", "T1", CAL_SH.calendar_id),
    B: Instrument("cat-B", "group-B", "T0", CAL_SH.calendar_id),
    C: Instrument("cat-C", "group-C", "T1", CAL_SZ.calendar_id),
    D: Instrument("cat-D", "group-D", "T1", CAL_SH.calendar_id),
}
CALENDARS = {c.calendar_id: c for c in (CAL_SH, CAL_SZ)}


def snapshot(*, cash=2000, equity=5000, volumes=None, pending=(), complete=True):
    volumes = {A: 1000, B: 1000, C: 1000} if volumes is None else volumes
    return AccountSnapshot(dec(equity), dec(cash),
        tuple(Position(s, q, q, dec(q)) for s, q in volumes.items() if q),
        tuple(pending), complete)


class RepairedPipeline(old.PipelineFixture):
    def __init__(self, symbols=None):
        super().__init__(symbols)
        self.risk_manager = ResearchRiskManager(self.config.risk,
            guard=FullAccountGuard(RULES, FEES), snapshot_loader=self.full_snapshot)

    def full_snapshot(self):
        # External broker inventory/order queries are replaced with explicit
        # fixture state. No pending SELL is credited as a completed exit.
        pending = []
        for oid, state in self.gateway.states.items():
            symbol, side, qty, price = self.xt_trader.orders[oid - 1]
            if side == "BUY" and state.remaining:
                pending.append(PendingBuy(str(oid), symbol, state.remaining, dec(price)))
        return snapshot(cash=self.xt_trader.cash, equity=self.xt_trader.asset,
                        volumes=self.xt_trader.volumes, pending=pending)

    def query_context(self, symbol, env):
        context = super().query_context(symbol, env)
        context.positions = {p.symbol: SymbolPosition(p.symbol, volume=p.volume,
            available_volume=p.available, market_value=float(p.market_value))
            for p in self.full_snapshot().positions}
        context.positions.setdefault(symbol, SymbolPosition(symbol))
        context.sync_legacy_fields(symbol)
        return context


class PipelineRepairTests(unittest.TestCase):
    def test_original_replacement_counterexample_now_respects_caps(self):
        adapter = RepairedPipeline()
        adapter._run_closing_auction_pipeline()
        self.assertEqual([o[:2] for o in adapter.xt_trader.orders], [(A, "SELL")])
        self.assertEqual(adapter.xt_trader.volumes, {A: 1000, B: 1000, C: 1000})
        self.assertEqual(sum(adapter.xt_trader.volumes.values()) / adapter.xt_trader.asset, .6)

    def test_sell_first_unfilled_does_not_release_capacity(self):
        adapter = RepairedPipeline([A, D, B, C])
        adapter._run_closing_auction_pipeline()
        self.assertEqual([o[:2] for o in adapter.xt_trader.orders], [(A, "SELL")])
        self.assertEqual(len(adapter.xt_trader.volumes), 3)

    def test_partial_exit_still_occupies_symbol_slot(self):
        adapter = RepairedPipeline()
        adapter.xt_trader.volumes[A] = 100
        adapter.xt_trader.cash = 2899.9
        adapter._run_closing_auction_pipeline()
        self.assertEqual([o[:2] for o in adapter.xt_trader.orders], [(A, "SELL")])
        self.assertNotIn(D, adapter.xt_trader.volumes)

    def test_confirmed_full_exit_allows_new_symbol(self):
        adapter = RepairedPipeline()
        adapter.xt_trader.volumes.pop(A)
        adapter.xt_trader.cash = 2999.9  # Confirmed exit, fee booked.
        adapter._run_closing_auction_pipeline()
        self.assertEqual([o[:2] for o in adapter.xt_trader.orders], [(D, "BUY")])
        self.assertEqual(adapter.xt_trader.volumes[D], 900)  # 1.1 limit price sizing
        self.assertEqual(len(adapter.xt_trader.volumes), 3)
        self.assertLessEqual(sum(adapter.xt_trader.volumes.values()) / adapter.xt_trader.asset, .6)

    def test_pipeline_repeat_keeps_single_submit_and_no_wait_cancel(self):
        adapter = RepairedPipeline()
        adapter._run_closing_auction_pipeline()
        adapter._run_closing_auction_pipeline()
        self.assertEqual(len(adapter.xt_trader.orders), 1)

    def test_full_context_not_single_symbol(self):
        adapter = RepairedPipeline()
        self.assertEqual(set(adapter.query_context(A, adapter.config.execution.env).positions), {A, B, C})

    def test_bridge_refreshes_even_when_original_context_is_incomplete(self):
        adapter = RepairedPipeline()
        context = old.PipelineFixture.query_context(adapter, D, adapter.config.execution.env)
        self.assertEqual(set(context.positions), {D})
        result = adapter.risk_manager.check_and_adjust(
            old.Signal(D, old.SignalAction.BUY, target_pct=.2, price=1), context)
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "max_symbols")
        self.assertTrue({A, B, C} <= context.positions.keys())

    def test_over_cap_account_still_permits_reducing_sell(self):
        adapter = RepairedPipeline([A, D, B, C])
        adapter.xt_trader.volumes[D] = 100
        adapter.xt_trader.cash = 1900
        result = adapter.risk_manager.check_and_adjust(old.Signal(A,
            old.SignalAction.SELL, target_volume=0, price=1), adapter.query_context(A, adapter.config.execution.env))
        self.assertTrue(result.ok)
        self.assertEqual(result.signal.target_volume, 0)

    def test_snapshot_loader_failure_blocks_buy(self):
        adapter = RepairedPipeline()
        def unavailable():
            raise ValueError("fixture_inventory_unavailable")
        adapter.risk_manager.snapshot_loader = unavailable
        result = adapter.risk_manager.check_and_adjust(old.Signal(D,
            old.SignalAction.BUY, target_pct=.2, price=1), old.StrategyContext(cash=0, available_cash=0, total_asset=5000))
        self.assertFalse(result.ok)
        self.assertIn("fixture_inventory_unavailable", result.reason)


class GuardRepairTests(unittest.TestCase):
    def setUp(self):
        self.guard = FullAccountGuard(RULES, FEES)

    def test_900_cash_buys_800_with_reserved_minimum_commission(self):
        plan = self.guard.plan_buy(snapshot(cash=900, volumes={}), D, 1, target_pct=.2)
        self.assertTrue(plan.allowed)
        self.assertEqual((plan.delta, plan.fee_reserve, plan.cash_reserve), (800, dec(".10"), dec("800.10")))

    def test_cash_exactly_gross_plus_fee_allows_900(self):
        plan = self.guard.plan_buy(snapshot(cash="900.10", volumes={}), D, 1, target_pct=.2)
        self.assertEqual(plan.delta, 900)

    def test_fee_one_cent_cash_boundary(self):
        plan = self.guard.plan_buy(snapshot(cash="900.09", volumes={}), D, 1, target_pct=.2)
        self.assertEqual(plan.delta, 800)

    def test_larger_explicit_minimum_fee_changes_sizing(self):
        guard = FullAccountGuard(RULES, FeeModel("SYNTHETIC-min-5", dec(".0001"), dec(5)))
        plan = guard.plan_buy(snapshot(cash=904, volumes={}), D, 1, target_pct=.2)
        self.assertEqual((plan.delta, plan.fee_reserve), (800, dec(5)))

    def test_rounding_reserve_is_upper_bound_on_actual_fee(self):
        fees = FeeModel("SYNTHETIC-rounding", dec(".000105"), dec(0))
        self.assertEqual(fees.commission(dec(1000)), dec(".11"))
        self.assertEqual(fees.commission(dec(999)), dec(".10"))
        self.assertEqual(fees.commission(dec(999), reserve=True), dec(".11"))

    def test_fees_are_in_post_cost_exposure_denominator(self):
        plan = self.guard.plan_buy(snapshot(cash=5000, volumes={}), D, 1, target_volume=1000)
        self.assertEqual(plan.delta, 900)
        self.assertEqual(plan.capital_basis, dec("4999.90"))
        self.assertLessEqual(plan.projected_value, plan.capital_basis * dec(".6"))

    def test_total_exposure_uses_all_old_positions(self):
        plan = self.guard.plan_buy(snapshot(volumes={A: 1400, B: 1400}, cash=2200), D, 1, target_pct=.2)
        self.assertEqual(plan.delta, 100)  # 200 would reach 3000 before fees.
        self.assertLessEqual(plan.projected_value, plan.capital_basis * dec(".6"))

    def test_no_blanket_pause_for_an_unfilled_exit_when_capacity_exists(self):
        # Two positions may include an unfilled SELL, but still occupy slots.
        plan = self.guard.plan_buy(snapshot(volumes={A: 500, B: 500}, cash=4000), D, 1, target_pct=.2)
        self.assertTrue(plan.allowed)
        self.assertEqual(plan.symbol_count, 3)

    def test_pending_unknown_buy_counts_toward_symbols(self):
        pending = (PendingBuy("unknown-submit", C, 100, dec(1)),)
        plan = self.guard.plan_buy(snapshot(volumes={A: 500, B: 500}, pending=pending), D, 1, target_pct=.2)
        self.assertFalse(plan.allowed)
        self.assertEqual(plan.reason, "max_symbols")

    def test_pending_buy_same_symbol_counted_once_and_not_reordered(self):
        pending = (PendingBuy("partial-order", D, 200, dec(1)),)
        plan = self.guard.plan_buy(snapshot(volumes={D: 100}, pending=pending, cash=4900), D, 1, target_volume=500)
        self.assertEqual((plan.symbol_count, plan.delta, plan.target_volume), (1, 200, 300))

    def test_pending_value_and_fees_consume_exposure(self):
        pending = (PendingBuy("unresolved", B, 900, dec(1)),)
        plan = self.guard.plan_buy(snapshot(volumes={A: 1900}, pending=pending, cash=3100), D, 1, target_pct=.2)
        self.assertEqual(plan.delta, 100)

    def test_broker_frozen_cash_is_not_reserved_twice(self):
        pending = (PendingBuy("broker-known", A, 500, dec(1), dec("500.10")),)
        plan = self.guard.plan_buy(snapshot(volumes={}, cash="900.10", pending=pending), D, 1, target_pct=.2)
        self.assertEqual(plan.delta, 900)

    def test_off_broker_and_partial_broker_reservations_reduce_cash(self):
        for frozen, expected in ((0, 300), ("200.10", 500)):
            with self.subTest(frozen=frozen):
                pending = (PendingBuy("unknown", A, 500, dec(1), dec(frozen)),)
                plan = self.guard.plan_buy(snapshot(volumes={}, cash=900, pending=pending), D, 1, target_pct=.2)
                self.assertEqual(plan.delta, expected)

    def test_capital_cap_and_actual_lower_equity(self):
        for equity, expected in ((6000, 1000), (4000, 700)):
            with self.subTest(equity=equity):
                plan = self.guard.plan_buy(snapshot(volumes={}, cash=equity, equity=equity), D, 1, target_pct=.2)
                self.assertEqual(plan.delta, expected)

    def test_group_and_category_overlap_reject_buy(self):
        for update in ({"group": RULES[A].group}, {"category": RULES[A].category}):
            with self.subTest(update=update):
                rules = dict(RULES)
                rules[D] = replace(rules[D], **update)
                plan = FullAccountGuard(rules, FEES).plan_buy(snapshot(volumes={A: 100}), D, 1, target_pct=.2)
                self.assertEqual(plan.reason, "category_or_group_limit")

    def test_incomplete_account_and_missing_product_metadata_reject(self):
        self.assertFalse(self.guard.plan_buy(snapshot(complete=False), D, 1, target_pct=.2).allowed)
        self.assertEqual(FullAccountGuard({D: RULES[D]}, FEES).plan_buy(
            snapshot(volumes={A: 100}), D, 1, target_pct=.2).reason, "missing_product_metadata")

    def test_duplicate_order_and_missing_raw_valuation_rejected(self):
        pending = PendingBuy("same", A, 100, dec(1))
        with self.assertRaises(ValueError):
            snapshot(pending=(pending, pending))
        with self.assertRaises(ValueError):
            Position(A, 100, 100, dec(0))

    def test_odd_existing_shares_buy_increment_remains_lot_sized(self):
        plan = self.guard.plan_buy(snapshot(volumes={D: 50}, cash=4950), D, 1, target_volume=350)
        self.assertEqual((plan.target_volume, plan.delta), (350, 300))

    def test_authoritative_buy_limit_not_price_cage_drives_reserve(self):
        guard = FullAccountGuard(RULES, FEES)
        risk = ResearchRiskManager(old.config().risk, guard=guard,
            snapshot_loader=lambda: snapshot(volumes={}, cash=900))
        result = risk.check_and_adjust(old.Signal(D, old.SignalAction.BUY, target_pct=.2, price=1.1),
            old.StrategyContext(cash=900, available_cash=900, total_asset=5000), old.MarketSnapshot(D, last_price=1))
        self.assertTrue(result.ok)
        self.assertEqual(result.signal.target_volume, 800)
        self.assertEqual(result.adjustments["cash_reserve"], "880.10")


class LedgerRepairTests(unittest.TestCase):
    def ledger(self, cash=5000, **kwargs):
        return ResearchLedger(cash=cash, day=FRI, instruments=RULES,
                              calendars=CALENDARS, fees=FEES, **kwargs)

    def test_original_fee_counterexample_now_guarded_and_executable(self):
        ledger = self.ledger(cash=900, balance_adjustment=4100)
        risk = ResearchRiskManager(old.config().risk, guard=FullAccountGuard(RULES, FEES),
                                   snapshot_loader=ledger.snapshot)
        result = risk.check_and_adjust(old.Signal(D, old.SignalAction.BUY, target_pct=.2, price=1),
                                      old.StrategyContext(cash=900, available_cash=900, total_asset=5000, date=old.NOW))
        self.assertTrue(result.ok)
        self.assertEqual(result.signal.target_volume, 800)
        self.assertTrue(ledger.execute(D, "BUY", result.signal.target_volume, 1).accepted)
        self.assertEqual((ledger.cash, ledger.snapshot().equity), (dec("99.90"), dec("4999.90")))

    def test_friday_buy_not_sellable_saturday_and_sellable_monday(self):
        ledger = self.ledger()
        self.assertTrue(ledger.execute(D, "BUY", 100, 1).accepted)
        ledger.advance_to(SAT)
        self.assertEqual(ledger.positions[D].available, 0)
        self.assertFalse(ledger.execute(D, "SELL", 100, 1).accepted)
        ledger.advance_to(MON)
        self.assertEqual(ledger.positions[D].available, 100)
        self.assertTrue(ledger.execute(D, "SELL", 100, 1).accepted)
        self.assertEqual(ledger.snapshot().equity, dec("4999.80"))

    def test_holiday_and_product_specific_calendar_used(self):
        ledger = self.ledger()
        self.assertTrue(ledger.execute(A, "BUY", 100, 1).accepted)
        self.assertTrue(ledger.execute(C, "BUY", 100, 1).accepted)
        ledger.advance_to(MON)
        self.assertEqual((ledger.positions[A].available, ledger.positions[C].available), (100, 0))
        ledger.advance_to(TUE)
        self.assertEqual(ledger.positions[C].available, 100)

    def test_mixed_t0_t1_same_account(self):
        ledger = self.ledger()
        self.assertTrue(ledger.execute(B, "BUY", 100, 1).accepted)
        self.assertTrue(ledger.execute(D, "BUY", 100, 1).accepted)
        self.assertTrue(ledger.execute(B, "SELL", 100, 1).accepted)
        self.assertFalse(ledger.execute(D, "SELL", 100, 1).accepted)

    def test_existing_available_shares_and_new_cohorts_separate(self):
        ledger = self.ledger(cash=4900, positions=(Position(D, 100, 100, dec(100)),), raw_prices={D: 1})
        self.assertTrue(ledger.execute(D, "BUY", 100, 1).accepted)
        self.assertEqual((ledger.positions[D].volume, ledger.positions[D].available), (200, 100))
        self.assertTrue(ledger.execute(D, "SELL", 100, 1).accepted)
        ledger.advance_to(MON)
        self.assertTrue(ledger.execute(D, "BUY", 100, 1).accepted)
        self.assertEqual((ledger.positions[D].volume, ledger.positions[D].available), (200, 100))
        ledger.advance_to(TUE)
        self.assertEqual(ledger.positions[D].available, 200)

    def test_cash_rejection_does_not_mutate_state(self):
        ledger = self.ledger(cash=900)
        before = ledger.snapshot()
        self.assertFalse(ledger.execute(D, "BUY", 900, 1).accepted)
        self.assertEqual(ledger.snapshot(), before)

    def test_calendar_missing_and_next_session_missing_fail_without_mutation(self):
        for calendars in ({}, {CAL_SH.calendar_id: TradingCalendar(CAL_SH.calendar_id, FRI, FRI, frozenset({FRI}))}):
            with self.subTest(calendars=list(calendars)):
                ledger = ResearchLedger(cash=5000, day=FRI, instruments=RULES, calendars=calendars, fees=FEES)
                before = ledger.snapshot()
                self.assertFalse(ledger.execute(D, "BUY", 100, 1).accepted)
                self.assertEqual(ledger.snapshot(), before)

    def test_out_of_coverage_advance_rejects_before_any_unlock(self):
        ledger = self.ledger()
        ledger.execute(D, "BUY", 100, 1)
        before = ledger.snapshot()
        with self.assertRaisesRegex(ValueError, "coverage"):
            ledger.advance_to(date(2026, 9, 21))
        self.assertEqual(ledger.day, FRI)
        self.assertEqual(ledger.snapshot(), before)
        self.assertEqual(ledger.positions[D].available, 0)

    def test_weekend_buy_and_backward_date_rejected(self):
        ledger = self.ledger()
        ledger.advance_to(SAT)
        self.assertFalse(ledger.execute(D, "BUY", 100, 1).accepted)
        with self.assertRaisesRegex(ValueError, "backward"):
            ledger.advance_to(FRI)

    def test_raw_marks_fees_cash_and_equity_reconcile(self):
        ledger = self.ledger()
        ledger.execute(D, "BUY", 900, 1)
        ledger.mark(D, "1.2")
        state = ledger.snapshot()
        self.assertEqual(state.equity, state.available_cash + sum(p.market_value for p in state.positions))
        self.assertEqual(state.equity, dec("5179.90"))

    def test_unknown_product_rule_rejects_and_does_not_guess_t1(self):
        ledger = self.ledger()
        before = ledger.snapshot()
        self.assertFalse(ledger.execute("unknown-product", "BUY", 100, 1).accepted)
        self.assertEqual(ledger.snapshot(), before)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_ids.append(test.id())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(TOPIC):
        raise SystemExit("Output must be a new versioned artifact inside the ETF topic")
    start = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    sources = [Path(__file__), Path(old.__file__),
               TOPIC / "baselines/etf_execution_repairs_v1.py",
               TOPIC / "baselines/etf_execution_bridge_v1.py"]
    payload = {"identity": "ETF-PHASE1-THREE-REPAIRS-L0-20260917-v1.0",
        "evidence_ceiling": "L0", "tests_run": result.testsRun, "passed": len(result.passed_ids),
        "passed_tests": result.passed_ids,
        "failures": [{"test": t.id(), "trace": trace} for t, trace in result.failures],
        "errors": [{"test": t.id(), "trace": trace} for t, trace in result.errors],
        "expected_failures": len(result.expectedFailures),
        "seconds": round(time.perf_counter() - start, 6),
        "sources": [{"path": str(p.relative_to(TOPIC)).replace("\\", "/"),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest().upper()} for p in sources],
        "fixture_scope": "Original indexed closing-auction/core/risk/request/SingleSubmitPolicy with offline broker; new research guard/ledger; all fees/product rules/calendars SYNTHETIC",
        "three_repair_gate_passed": result.wasSuccessful(), "phase1_gate_passed": False,
        "unrepaired_clock_contracts": ["quote_future_tolerance_vs_request_start", "captured_at_is_request_start_not_received_at"],
        "formal_backtests": 0, "locked_results_opened": 0, "simulation_authorizations": 0,
        "live_trading_authorizations": 0, "application_modified": False}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
