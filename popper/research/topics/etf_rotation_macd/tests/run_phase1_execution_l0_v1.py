"""Offline tests of the indexed snapshot; expected failures retain charter gaps.

No adapter constructor, SDK, network, real account or order API is invoked.
ShadowAccount persists only to TemporaryDirectory. The pipeline test replaces
external broker state and router handoff with an explicit deterministic fixture.
It is not a production integration test or a formal backtest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
TOPIC = ROOT / "research/topics/etf_rotation_macd"
ENGINE = ROOT.parents[1] / "FINITUDE-1.4.2/sartre"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ENGINE))

from sartre_core.adapters.miniqmt_closing_auction_mixin import MiniQMTClosingAuctionMixin
from sartre_core.adapters.miniqmt_market_account_mixin import MiniQMTMarketAccountMixin
from sartre_core.adapters.miniqmt_portfolio_mixin import MiniQMTPortfolioMixin
from sartre_core.adapters.miniqmt_stock_execution_mixin import MiniQMTStockExecutionMixin
from sartre_core.config import UnifiedStrategyConfig
from sartre_core.engine import MarketSnapshot, Signal, SignalAction, StrategyContext
from sartre_core.engine.order_policies import OrderState, OrderSubmission, SingleSubmitPolicy
from sartre_core.simulate.shadow_account import FeeSchedule, ShadowAccount
from sartre_core.strategies.etf_rotation_core import ETFRotationCoreStrategy
from sartre_risk import RiskManager

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 9, 14, 57, 35, tzinfo=TZ)
A, B, C, D = "510001.SH", "512001.SH", "159001.SZ", "510004.SH"


def config(symbols=None):
    cfg = UnifiedStrategyConfig.from_dict({
        "symbols": symbols or [D, A, B, C],
        "risk": {"max_total_position_pct": 0.6, "max_symbol_position_pct": 0.2, "lot_size": 100, "enable_t1": True, "price_cage_ratio": 0.02, "tick_size": 0.001, "max_open_per_day": 3, "max_close_per_day": 3},
        "execution": {"env": "sim", "strategy_id": "etf_rotation_core", "asset_type": "etf", "max_cash": 5000},
    })
    cfg.disable_intraday_target_refresh = True
    return cfg


class LogFixture:
    def __getattr__(self, name):
        if name.startswith("log_"):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class BrokerFixture:
    """5000 account, three old ETFs; buys fill and exit sell stays unfilled."""
    def __init__(self):
        self.cash = 2000.0
        self.volumes = {A: 1000, B: 1000, C: 1000}
        self.orders = []

    @property
    def asset(self):
        return self.cash + sum(self.volumes.values())

    def query_stock_asset(self, unused):
        return SimpleNamespace(cash=self.cash, total_asset=self.asset)

    def query_stock_positions(self, unused):
        return [SimpleNamespace(stock_code=s, volume=v, can_use_volume=v, avg_price=1.0, market_value=float(v)) for s, v in self.volumes.items()]


class GatewayFixture:
    def __init__(self, broker):
        self.broker = broker
        self.states = {}

    def submit(self, request, *, volume, attempt_no):
        oid = len(self.broker.orders) + 1
        filled = request.signal.action == SignalAction.BUY
        if filled:
            self.broker.cash -= volume + 0.1
            self.broker.volumes[request.symbol] = self.broker.volumes.get(request.symbol, 0) + volume
        self.broker.orders.append((request.symbol, request.signal.action.value, volume, request.limit_price))
        self.states[oid] = OrderState(oid, volume, volume if filled else 0, 0 if filled else volume, "COMPLETED" if filled else "PENDING", "offline_fixture")
        return OrderSubmission(oid, oid)

    def inspect(self, request, *, order_id, order_volume):
        return self.states[order_id]

    def wait(self, *args, **kwargs):
        raise AssertionError("single_submit must not wait")

    def cancel_and_confirm(self, *args, **kwargs):
        raise AssertionError("single_submit must not cancel")


class PipelineFixture(MiniQMTClosingAuctionMixin, MiniQMTStockExecutionMixin, MiniQMTMarketAccountMixin, MiniQMTPortfolioMixin):
    def __init__(self, symbols=None):
        self.config = config(symbols)
        self.strategy_core = ETFRotationCoreStrategy(target_pct_map={A: 0, B: 0.2, C: 0.2, D: 0.2})
        self.risk_manager = RiskManager(self.config.risk)
        self.xt_trader = BrokerFixture()
        self.xt_acc = object()  # Offline token, not an account identifier.
        self.gateway = GatewayFixture(self.xt_trader)
        self.xtconstant = SimpleNamespace(STOCK_BUY=23, STOCK_SELL=24)
        self._shadow_account = None
        self.logger = LogFixture()
        self._target_refresh_date = NOW.date().isoformat()
        self._etf_target_gate_logged_date = ""
        self._closing_auction_state_date = ""
        for field in ["candidates", "decisions", "outcomes", "last_market_status", "price_limits_cache"]:
            setattr(self, "_closing_auction_" + field, {})
        for field in ["processed_keys", "summary_logged", "audit_keys", "attempted"]:
            setattr(self, "_closing_auction_" + field, set())

    def _now(self):
        return NOW

    def _execution_module_settings(self, name):
        return {"submit_start": "14:57:30", "submit_end": "15:00:00", "max_tick_age_seconds": 5}

    def _tick_is_paused(self, tick):
        return False

    def _closing_auction_price_limits(self, symbol, tick):
        return 1.1, 0.9

    def query_full_tick(self, symbols, force_refresh=False):
        return {s: {"symbol": s, "time": int(NOW.timestamp() * 1000), "lastPrice": 1.0, "stockStatus": 18, "openInt": 18, "lastClose": 1.0, "bidPrice": [1.0], "askPrice": [1.0]} for s in symbols}

    def query_context(self, symbol, env):
        context = super().query_context(symbol, env)
        context.date = NOW  # Explicit fixture clock for offline historical date.
        return context

    def _log_strategy_daily_event(self, **kwargs):
        pass

    def execute_signal(self, signal, context, snapshot):
        return self.execute_closing_auction_signal(signal, context, snapshot)

    def _execute_signal_with_order_policy(self, **kwargs):
        # The production request builder and single-submit policy are used;
        # external router/gateway are replaced to guarantee no real orders.
        request = self._build_execution_request(
            signal=kwargs["signal"], context=kwargs["context"], snapshot=kwargs["snapshot"],
            module_name=kwargs["module_name"], policy_name=kwargs["policy_name"],
            broker_action=kwargs["broker_action"], action_label=kwargs["action_label"],
            price=kwargs["price"], window_start=kwargs["window_start"], window_end=kwargs["window_end"],
            idempotency_key=kwargs["idempotency_key"], now=NOW,
        )
        result = SingleSubmitPolicy(now_fn=lambda: NOW).execute(request, self.gateway)
        return {"status": result.status, "order_volume": request.requested_volume, "traded_volume": result.traded_volume}


class PipelineTests(unittest.TestCase):
    def test_context_contains_only_current_symbol(self):
        adapter = PipelineFixture()
        context = adapter.query_context(A, adapter.config.execution.env)
        self.assertEqual(set(context.positions), {A})
        self.assertEqual(len(adapter.xt_trader.query_stock_positions(None)), 3)

    def test_actual_pipeline_accepts_buy_while_exit_remains_unfilled(self):
        adapter = PipelineFixture()
        adapter._run_closing_auction_pipeline()
        self.assertEqual([o[:2] for o in adapter.xt_trader.orders], [(D, "BUY"), (A, "SELL")])
        self.assertEqual(adapter.xt_trader.volumes[D], 900)
        self.assertEqual(adapter.xt_trader.volumes[A], 1000)
        self.assertGreater(sum(adapter.xt_trader.volumes.values()) / adapter.xt_trader.asset, 0.6)

    def test_sell_first_submission_still_does_not_wait_for_fill(self):
        adapter = PipelineFixture([A, D, B, C])
        adapter._run_closing_auction_pipeline()
        self.assertEqual([o[1] for o in adapter.xt_trader.orders], ["SELL", "BUY"])
        self.assertEqual(len(adapter.xt_trader.volumes), 4)

    @unittest.expectedFailure
    def test_charter_full_account_caps_hold_during_unfilled_replacement(self):
        adapter = PipelineFixture()
        adapter._run_closing_auction_pipeline()
        self.assertLessEqual(len([v for v in adapter.xt_trader.volumes.values() if v > 0]), 3)
        self.assertLessEqual(sum(adapter.xt_trader.volumes.values()) / adapter.xt_trader.asset, 0.6)

    def test_repeat_pipeline_submits_once_per_symbol(self):
        adapter = PipelineFixture()
        adapter._run_closing_auction_pipeline()
        adapter._run_closing_auction_pipeline()
        self.assertEqual(len(adapter.xt_trader.orders), 2)

    def test_targets_not_refreshed_block_pipeline(self):
        adapter = PipelineFixture()
        adapter._target_refresh_date = ""
        adapter._run_closing_auction_pipeline()
        self.assertEqual(adapter.xt_trader.orders, [])

    def test_old_quote_and_wrong_market_state_fail_closed(self):
        adapter = PipelineFixture()
        tick = adapter.query_full_tick([D])[D]
        for update in [{"time": int((NOW - timedelta(seconds=6)).timestamp() * 1000)}, {"stockStatus": 13, "openInt": 13}]:
            allowed, *unused = adapter._closing_auction_eligibility(symbol=D, tick={**tick, **update}, now=NOW)
            self.assertFalse(allowed)

    @unittest.expectedFailure
    def test_confirmed_price_information_set_rejects_future_quote(self):
        adapter = PipelineFixture()
        tick = adapter.query_full_tick([D])[D]
        tick["time"] = int((NOW + timedelta(seconds=2)).timestamp() * 1000)
        allowed, *unused = adapter._closing_auction_eligibility(symbol=D, tick=tick, now=NOW)
        self.assertFalse(allowed)


class ShadowLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="etf_phase1_l0_")
        self.clock = [NOW]

    def tearDown(self):
        self.temp.cleanup()

    def account(self, cash=5000, t1=True, positions=None, total=None):
        account = ShadowAccount(Path(self.temp.name) / "offline.json", enable_t1=t1, now=lambda: self.clock[0])
        account.initialize_once(lambda: {"cash": cash, "total_asset": total if total is not None else cash}, lambda: positions or [])
        return account

    def trade(self, account, side, volume=100, price=1):
        return account.execute_trade(symbol=D, side=side, volume=volume, price=price, asset_type="etf")

    def test_cash_equity_fees_and_full_positions_reconcile(self):
        account = self.account()
        bought = self.trade(account, "BUY", 900)
        state = account.snapshot()
        self.assertTrue(bought.accepted)
        self.assertAlmostEqual(state.cash, 4099.9)
        self.assertAlmostEqual(state.total_asset, 4999.9)
        self.assertAlmostEqual(state.total_asset, state.cash + sum(p.market_value for p in state.positions.values()) + state.balance_adjustment)
        self.assertEqual((bought.commission, bought.stamp_tax), (0.1, 0.0))

    def test_same_day_t1_sell_rejected_next_day_sell_reconciles(self):
        account = self.account()
        self.assertTrue(self.trade(account, "BUY").accepted)
        self.assertFalse(self.trade(account, "SELL").accepted)
        self.clock[0] += timedelta(days=1)
        self.assertTrue(self.trade(account, "SELL").accepted)
        self.assertAlmostEqual(account.snapshot().total_asset, 4999.8)

    def test_t0_flag_allows_same_day_sale(self):
        account = self.account(t1=False)
        self.assertTrue(self.trade(account, "BUY").accepted)
        self.assertTrue(self.trade(account, "SELL").accepted)

    def test_fee_cash_rejection_does_not_change_account(self):
        account = self.account(cash=900)
        before = account.snapshot()
        self.assertFalse(self.trade(account, "BUY", 900).accepted)
        after = account.snapshot()
        self.assertEqual((after.cash, after.total_asset, after.positions), (before.cash, before.total_asset, before.positions))

    @unittest.expectedFailure
    def test_execution_sizing_reserves_commission_when_cash_exactly_matches_lot(self):
        cfg = config()
        context = StrategyContext(cash=900, available_cash=900, total_asset=5000, date=NOW)
        risk = RiskManager(cfg.risk).check_and_adjust(Signal(symbol=D, action=SignalAction.BUY, target_pct=0.2, price=1.0), context, MarketSnapshot(symbol=D, last_price=1.0))
        self.assertTrue(risk.ok)
        account = self.account(cash=900, total=5000)
        self.assertTrue(self.trade(account, "BUY", risk.signal.target_volume).accepted)

    @unittest.expectedFailure
    def test_t1_does_not_unlock_on_nontrading_calendar_day(self):
        self.clock[0] = datetime(2026, 9, 11, 14, 57, 35, tzinfo=TZ)  # Friday
        account = self.account()
        self.assertTrue(self.trade(account, "BUY").accepted)
        self.clock[0] += timedelta(days=1)  # Saturday, not an exchange session
        self.assertEqual(account.snapshot().positions[D].available_volume, 0)

    def test_initial_balance_adjustment_is_explicit(self):
        account = self.account(cash=2000, total=5000, positions=[{"stock_code": A, "volume": 1000, "can_use_volume": 1000, "market_value": 1000}])
        self.assertEqual(account.snapshot().balance_adjustment, 2000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(TOPIC):
        raise SystemExit("Output must be a new versioned artifact inside the ETF topic")
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    start = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    payload = {"identity": "ETF-PHASE1-EXECUTION-L0-20260916-v1.0", "evidence_ceiling": "L0", "formal_backtests": 0, "tests_run": result.testsRun, "passed": result.testsRun - len(result.expectedFailures) - len(result.failures) - len(result.errors) - len(result.unexpectedSuccesses), "retained_contract_failures": [test.id() for test, trace in result.expectedFailures], "unexpected_failures": [test.id() for test, trace in result.failures], "errors": [test.id() for test, trace in result.errors], "unexpected_successes": [test.id() for test in result.unexpectedSuccesses], "seconds": round(time.perf_counter() - start, 6), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(), "fixture_scope": "Real core, per-symbol context/sync, risk, closing-auction pipeline/request and SingleSubmitPolicy; offline broker states and router handoff; shadow-account tests use temporary files only", "charter_gate_passed": False}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
