from __future__ import annotations

import hashlib
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


POPPER_ROOT = Path(__file__).resolve().parents[4]
SARTRE_ROOT = POPPER_ROOT.parents[1] / "FINITUDE-1.4.2" / "sartre"
ETF_CORE_PATH = SARTRE_ROOT / "sartre_core" / "strategies" / "etf_rotation_core.py"
MACD_CORE_PATH = SARTRE_ROOT / "sartre_core" / "strategies" / "macd_core.py"
CONFIG_PATH = SARTRE_ROOT / "sartre_core" / "config" / "etf_rotation_config.json"
BACKTRADER_PATH = SARTRE_ROOT / "sartre_core" / "adapters" / "backtrader_adapter.py"
ETF_RUNNER_PATH = SARTRE_ROOT / "run" / "run_etf_backtest.py"
MINIQMT_AUCTION_PATH = SARTRE_ROOT / "sartre_core" / "adapters" / "miniqmt_closing_auction_mixin.py"

EXPECTED_HASHES = {
    ETF_CORE_PATH: "1F7006FC7240157840E928DD6EE1DFDC50868331F26A16506A31A1EE38884317",
    MACD_CORE_PATH: "C2199714C1DD3C848F72E6E05A67BB8F1788C8442AC5188CCBCFC4E84E8155E7",
    CONFIG_PATH: "8E14BC5BFEA0429158740E93308A6261BD2530429B4B697D8683770E2F6F355D",
}

if not SARTRE_ROOT.exists():
    raise RuntimeError(f"Verified FINITUDE snapshot is missing: {SARTRE_ROOT}")
sys.path.insert(0, str(SARTRE_ROOT))

from sartre_core.adapters.backtrader_adapter import BacktraderAdapter
from sartre_core.adapters.miniqmt_portfolio_mixin import MiniQMTPortfolioMixin
from sartre_core.config import UnifiedStrategyConfig
from sartre_core.config.runtime_config import validate_realtime_config
from sartre_core.data.schemas import normalize_canonical_bars
from sartre_core.engine import MarketSnapshot, Signal, SignalAction, StrategyContext, SymbolPosition
from sartre_core.strategies.etf_rotation_core import (
    ETFRotationCoreStrategy,
    ETFRotationParams,
    _build_indicator_snapshot,
    _held_exit_reason,
    load_etf_rotation_params,
    select_etf_portfolio,
)
from sartre_core.strategies.macd_core import MACDStrategyParams
from sartre_risk import RiskManager


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _ranked_rows(count: int = 8) -> pd.DataFrame:
    categories = ["broad", "industry", "theme", "cross_border", "bond_money_commodity"]
    rows = []
    for rank in range(1, count + 1):
        category = categories[(rank - 1) % len(categories)]
        rows.append(
            {
                "as_of_date": "2026-07-08",
                "symbol": f"{510000 + rank}.SH",
                "name": f"ETF-{rank}",
                "category": category,
                "tracking_index": f"IDX-{rank}",
                "group": f"GROUP-{rank}",
                "score": float(100 - rank),
                "rank": rank,
                "rank_value": rank,
                "trend_ok": True,
                "trend_status": "uptrend",
                "filter_reason": "",
                "close": 10.0,
                "ma_short": 9.0,
                "ma_long": 8.0,
            }
        )
    return pd.DataFrame(rows)


class SnapshotIdentityTests(unittest.TestCase):
    def test_snapshot_hashes_are_frozen(self) -> None:
        for path, expected in EXPECTED_HASHES.items():
            self.assertTrue(path.exists(), path)
            self.assertEqual(_sha256(path), expected)

    def test_confirmed_config_contract(self) -> None:
        params = load_etf_rotation_params(CONFIG_PATH)
        self.assertEqual((params.period, params.adjust), ("1d", "qfq"))
        self.assertEqual((params.ma_short, params.ma_long), (20, 60))
        self.assertEqual(
            (params.score_short_window, params.score_long_window, params.score_vol_window),
            (20, 60, 20),
        )
        self.assertEqual((params.buy_rank_top_n, params.sell_rank_keep_n), (5, 15))
        self.assertEqual((params.max_holdings, params.group_cap), (3, 1))
        self.assertEqual(
            (params.target_position_pct, params.max_symbol_position_pct, params.max_total_position_pct),
            (0.2, 0.2, 0.6),
        )
        self.assertTrue(all(cap == 1 for cap in params.category_caps.values()))
        self.assertEqual(params.rank_time, "14:57:00")
        self.assertEqual(params.execution_pipeline, "closing_auction")


class RankingAndTrendTests(unittest.TestCase):
    def test_indicator_uses_as_of_bar_close_above_ma20_not_ma20_above_ma60(self) -> None:
        dates = pd.date_range(end="2026-07-08", periods=61, freq="D")
        closes = [100.0] * 41 + [50.0] * 19 + [60.0]
        bars = pd.DataFrame(
            {
                "datetime": list(dates) + [pd.Timestamp("2026-07-09")],
                "close": closes + [999.0],
                "amount": [1_000_000.0] * 62,
                "volume": [100_000.0] * 62,
            }
        )
        params = ETFRotationParams()
        snapshot = _build_indicator_snapshot(bars, params, date(2026, 7, 8))
        self.assertEqual(snapshot["close"], 60.0)
        self.assertGreater(snapshot["close"], snapshot["ma_short"])
        self.assertLess(snapshot["close"], snapshot["ma_long"])
        self.assertTrue(snapshot["trend_ok"])

        close = pd.Series(closes, dtype="float64")
        returns = close.pct_change()
        expected_score = (
            close.iloc[-1] / close.iloc[-21] - 1.0
            + close.iloc[-1] / close.iloc[-61] - 1.0
            - returns.dropna().tail(20).std()
        ) * 100.0
        self.assertAlmostEqual(snapshot["score"], expected_score, places=12)

    def test_held_position_exits_below_ma20(self) -> None:
        row = SimpleNamespace(
            symbol="510001.SH",
            group="GROUP-1",
            close=9.9,
            ma_short=10.0,
            ma_long=8.0,
            trend_ok=True,
            rank_value=1,
            score=10.0,
        )
        self.assertEqual(
            _held_exit_reason(row, pd.DataFrame(), ETFRotationParams()),
            "exit:close_below_ma20",
        )


class PortfolioConstructionTests(unittest.TestCase):
    def test_new_entries_are_limited_to_top_n_and_rank_fill_is_unreachable(self) -> None:
        params = ETFRotationParams(
            buy_rank_top_n=2,
            max_holdings=4,
            max_total_position_pct=0.8,
            category_caps={key: 4 for key in ETFRotationParams().category_caps},
            group_cap=4,
        )
        selected, _targets = select_etf_portfolio(
            _ranked_rows(),
            current_symbols=[],
            params=params,
            as_of_date=date(2026, 7, 8),
        )
        self.assertEqual(selected["rank"].astype(int).tolist(), [1, 2])
        self.assertNotIn("entry:rank_fill", set(selected["selection_reason"]))

    def test_top15_hysteresis_and_all_portfolio_caps_survive(self) -> None:
        ranked = _ranked_rows(15)
        retained_symbol = str(ranked.loc[9, "symbol"])
        selected, targets = select_etf_portfolio(
            ranked,
            current_symbols=[retained_symbol],
            params=ETFRotationParams(),
            as_of_date=date(2026, 7, 8),
        )
        positive = targets[targets["target_pct"] > 0].copy()
        self.assertIn(retained_symbol, set(positive["symbol"]))
        self.assertLessEqual(len(positive), 3)
        self.assertTrue((positive["target_pct"] <= 0.2 + 1e-12).all())
        self.assertLessEqual(float(positive["target_pct"].sum()), 0.6 + 1e-12)
        self.assertTrue((positive.groupby("category").size() <= 1).all())
        self.assertTrue((positive.groupby("group").size() <= 1).all())
        retained = selected[selected["symbol"] == retained_symbol].iloc[0]
        self.assertEqual(retained["selection_reason"], "hold:kept")


class ExecutionContractTests(unittest.TestCase):
    def _context(self, *, volume: int, available: int, price: float = 10.0) -> StrategyContext:
        return StrategyContext(
            cash=100_000.0,
            available_cash=100_000.0,
            total_asset=100_000.0,
            positions={
                "510001.SH": SymbolPosition(
                    symbol="510001.SH",
                    volume=volume,
                    available_volume=available,
                    market_value=volume * price,
                )
            },
        )

    def test_target_tolerance_and_t1_available_volume(self) -> None:
        params = ETFRotationParams(target_tolerance_pct=0.01)
        strategy = ETFRotationCoreStrategy(params=params, target_pct_map={"510001.SH": 0.2})
        frame = pd.DataFrame({"close": [10.0]})

        matched = strategy.generate_signal(
            "510001.SH", frame, self._context(volume=1_950, available=1_950), drop_last_bar=False
        )
        self.assertEqual(matched.action, SignalAction.HOLD)

        overweight_t1_locked = strategy.generate_signal(
            "510001.SH", frame, self._context(volume=2_200, available=0), drop_last_bar=False
        )
        self.assertEqual(overweight_t1_locked.action, SignalAction.HOLD)

        config = UnifiedStrategyConfig.from_dict(
            {
                "risk": {
                    "max_total_position_pct": 0.6,
                    "max_symbol_position_pct": 0.2,
                    "lot_size": 100,
                    "enable_t1": True,
                }
            }
        )
        result = RiskManager(config.risk).check_and_adjust(
            Signal(symbol="510001.SH", action=SignalAction.SELL, target_pct=0.0, price=10.0),
            self._context(volume=2_200, available=0),
            MarketSnapshot(symbol="510001.SH", last_price=10.0),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "sell_target_not_below_current")

    def test_backtrader_scaling_keeps_default_account_targets(self) -> None:
        adapter = BacktraderAdapter.__new__(BacktraderAdapter)
        adapter.config = SimpleNamespace(
            target_position_pct_map={
                "510001.SH": 0.2,
                "510002.SH": 0.2,
                "510003.SH": 0.2,
            },
            risk=SimpleNamespace(max_total_position_pct=0.6, max_symbol_position_pct=0.2),
        )
        signals = [
            Signal(symbol=symbol, action=SignalAction.BUY, target_pct=0.2)
            for symbol in adapter.config.target_position_pct_map
        ]
        scaled = adapter._scale_portfolio_target_pct(signals)
        for signal in scaled:
            self.assertAlmostEqual(float(signal.target_pct), 0.2)
        self.assertAlmostEqual(sum(float(signal.target_pct) for signal in scaled), 0.6)

        adapter.config.target_position_pct_map = {"510001.SH": 0.2}
        one = adapter._scale_portfolio_target_pct(signals[:1])
        self.assertEqual(one[0].target_pct, 0.2)

    def test_backtest_targets_refresh_once_per_date_and_defer_buys_on_exit_day(self) -> None:
        calls: list[dict] = []

        class Core:
            def refresh_target_positions(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(
                    ranked=pd.DataFrame([{"symbol": "510001.SH"}]),
                    selected=pd.DataFrame([{"symbol": "510001.SH"}]),
                    target_positions=pd.DataFrame(
                        [{"symbol": "510001.SH", "target_pct": 0.2}]
                    ),
                )

        class Logger:
            def log_event(self, _payload):
                return None

        adapter = BacktraderAdapter.__new__(BacktraderAdapter)
        adapter.config = SimpleNamespace(
            execution=SimpleNamespace(env=SimpleNamespace(value="backtest"), strategy_id="etf_rotation_core")
        )
        adapter.strategy_core = Core()
        adapter.logger = Logger()
        adapter._backtest_target_refresh_date = None
        data = SimpleNamespace(_name="510001.SH")

        class FakeBT:
            datas = [data]

            @staticmethod
            def getposition(_data):
                return SimpleNamespace(size=100)

        bt = FakeBT()
        adapter._refresh_backtest_strategy_targets(bt, date(2026, 7, 8))
        adapter._refresh_backtest_strategy_targets(bt, date(2026, 7, 8))
        adapter._refresh_backtest_strategy_targets(bt, date(2026, 7, 9))
        self.assertEqual(len(calls), 2)
        self.assertEqual([call["as_of_date"] for call in calls], [date(2026, 7, 8), date(2026, 7, 9)])
        self.assertTrue(all(call["skip_download"] for call in calls))

        exit_context = self._context(volume=100, available=100)
        tasks = [
            {"symbol": "510001.SH", "context": exit_context},
            {
                "symbol": "510002.SH",
                "context": StrategyContext(
                    cash=100_000.0,
                    available_cash=100_000.0,
                    total_asset=100_000.0,
                ),
            },
        ]
        deferred = adapter._defer_backtest_buys_until_exits_clear(
            tasks,
            [
                Signal(symbol="510001.SH", action=SignalAction.SELL, target_pct=0.0),
                Signal(symbol="510002.SH", action=SignalAction.BUY, target_pct=0.2),
            ],
        )
        self.assertEqual(deferred[0].action, SignalAction.SELL)
        self.assertEqual(deferred[1].action, SignalAction.HOLD)
        self.assertEqual(deferred[1].reason, "defer_buy_until_exit_complete")

    def test_realtime_timing_config_is_valid_and_backtest_order_is_next_bar_market(self) -> None:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["etf_rotation"]["strategy"]["rank_time"], "14:57:00")
        auction = payload["execution_modules"]["closing_auction"]
        self.assertEqual((auction["submit_start"], auction["submit_end"]), ("14:57:30", "15:00:00"))
        self.assertEqual(auction["order_policy"], "single_submit")

        config = UnifiedStrategyConfig.from_json_file(CONFIG_PATH)
        config.symbols = ["510001.SH"]
        validate_realtime_config(config)

        source = BACKTRADER_PATH.read_text(encoding="utf-8")
        next_body = source[source.index("class UnifiedBTStrategy"):source.index("def notify_order", source.index("class UnifiedBTStrategy"))]
        self.assertLess(
            next_body.index("_refresh_backtest_strategy_targets"),
            next_body.index("strategy_core.generate_signal"),
        )
        self.assertIn("drop_last_bar=False", next_body)
        self.assertIn("order_target_percent", next_body)

    def test_config_exposes_ranking_and_backtest_price_contract_mismatch(self) -> None:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual((payload["data"]["period"], payload["data"]["adjust"]), ("1d", "qfq"))
        self.assertEqual(
            (payload["backtest"]["period"], payload["backtest"]["adjust"]),
            ("1h", "none"),
        )
        runner_source = ETF_RUNNER_PATH.read_text(encoding="utf-8").replace("\\", "/")
        self.assertIn('"csv" / "1d" / "qfq"', runner_source)

    def test_exit_before_entry_behavior_differs_between_backtest_and_generic_miniqmt_batch(self) -> None:
        exit_context = self._context(volume=100, available=100)
        buy_context = StrategyContext(
            cash=100_000.0,
            available_cash=100_000.0,
            total_asset=100_000.0,
        )
        tasks = [
            {"symbol": "510001.SH", "context": exit_context},
            {"symbol": "510002.SH", "context": buy_context},
        ]
        signals = [
            Signal(symbol="510001.SH", action=SignalAction.SELL, target_pct=0.0),
            Signal(symbol="510002.SH", action=SignalAction.BUY, target_pct=0.2),
        ]

        backtest = BacktraderAdapter.__new__(BacktraderAdapter)
        backtest.config = SimpleNamespace(
            execution=SimpleNamespace(env=SimpleNamespace(value="backtest"), strategy_id="etf_rotation_core")
        )
        bt_result = backtest._defer_backtest_buys_until_exits_clear(tasks, signals)

        miniqmt = MiniQMTPortfolioMixin.__new__(MiniQMTPortfolioMixin)
        miniqmt.config = SimpleNamespace(execution=SimpleNamespace(asset_type="etf"))
        miniqmt.strategy_core = SimpleNamespace(params=SimpleNamespace(max_holdings=3))
        miniqmt.query_current_position_symbols = lambda: ["510001.SH"]
        mini_result = miniqmt._defer_buys_until_exits_clear(tasks, signals)

        self.assertEqual(bt_result[1].action, SignalAction.HOLD)
        self.assertEqual(mini_result[1].action, SignalAction.BUY)

    def test_legacy_normalization_relabels_daily_qfq_without_converting_prices_or_frequency(self) -> None:
        daily_qfq = pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2026-07-08", "2026-07-09"]),
                "symbol": ["510001.SH", "510001.SH"],
                "open": [1.0, 1.1],
                "high": [1.1, 1.2],
                "low": [0.9, 1.0],
                "close": [1.05, 1.15],
                "volume": [1000.0, 2000.0],
                "period": ["1d", "1d"],
                "adjust": ["qfq", "qfq"],
            }
        )
        normalized = normalize_canonical_bars(daily_qfq, period="1h", adjust="none")
        self.assertEqual(normalized["period"].tolist(), ["1h", "1h"])
        self.assertEqual(normalized["adjust"].tolist(), ["none", "none"])
        self.assertEqual(normalized["datetime"].tolist(), daily_qfq["datetime"].tolist())
        for field in ("open", "high", "low", "close", "volume"):
            self.assertEqual(normalized[field].tolist(), daily_qfq[field].tolist())

    def test_miniqmt_5000_is_capped_asset_and_cash_not_uncapped_compounding(self) -> None:
        miniqmt = MiniQMTPortfolioMixin.__new__(MiniQMTPortfolioMixin)
        miniqmt.config = SimpleNamespace(execution=SimpleNamespace(max_cash=5000.0))
        self.assertEqual(miniqmt._execution_total_asset(100_000.0), 5000.0)
        self.assertEqual(miniqmt._execution_total_asset(5004.0), 5000.0)
        self.assertEqual(miniqmt._execution_total_asset(4900.0), 4900.0)
        self.assertEqual(miniqmt._execution_available_cash(8000.0, reserved_cash=200.0), 4800.0)
        self.assertEqual(miniqmt._execution_available_cash(4000.0), 4000.0)

    def test_miniqmt_5000_auction_buy_sizes_at_upper_limit_then_rounds_to_100(self) -> None:
        config = UnifiedStrategyConfig.from_dict(
            {"risk": {"max_total_position_pct": 0.6, "max_symbol_position_pct": 0.2, "lot_size": 100}}
        )
        context = StrategyContext(cash=5000.0, available_cash=5000.0, total_asset=5000.0)
        result = RiskManager(config.risk).check_and_adjust(
            Signal(symbol="510001.SH", action=SignalAction.BUY, target_pct=0.2, price=1.1),
            context,
            MarketSnapshot(symbol="510001.SH", last_price=1.0),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.signal.target_volume, 900)

        # A hypothetical 11-yuan upper limit prevents even one 100-unit lot,
        # despite a 10-yuan proxy last price fitting the nominal 1000-yuan target.
        blocked = RiskManager(config.risk).check_and_adjust(
            Signal(symbol="510001.SH", action=SignalAction.BUY, target_pct=0.2, price=11.0),
            context,
            MarketSnapshot(symbol="510001.SH", last_price=10.0),
        )
        self.assertFalse(blocked.ok)
        self.assertEqual(blocked.reason, "buy_target_not_above_current")

    def test_configured_closing_auction_does_not_use_generic_batch_scaling_or_exit_deferral(self) -> None:
        source = MINIQMT_AUCTION_PATH.read_text(encoding="utf-8")
        auction_body = source[source.index("    def _run_closing_auction_pipeline("):]
        self.assertIn("for raw_symbol in self.config.symbols:", auction_body)
        self.assertIn("price=limit_price", auction_body)
        self.assertIn("self._risk_check_and_adjust(", auction_body)
        self.assertIn("self.execute_signal(", auction_body)
        self.assertNotIn("_scale_portfolio_target_pct(", auction_body)
        self.assertNotIn("_defer_buys_until_exits_clear(", auction_body)

    def test_macd_candidate_family_is_fixed_but_not_integrated_into_baseline(self) -> None:
        params = MACDStrategyParams()
        self.assertEqual((params.macd_fast, params.macd_slow, params.macd_signal), (12, 26, 9))
        etf_source = ETF_CORE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("MACDCoreStrategy", etf_source)
        self.assertNotIn("macd_fast", etf_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
