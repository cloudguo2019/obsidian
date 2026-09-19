"""Offline receipt-time contract tests; in-memory fetcher and store only."""
import argparse
import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOPIC = ROOT / "research/topics/etf_rotation_macd"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT.parents[1] / "FINITUDE-1.4.2/sartre"))
from sartre_core.data.market_tick import MarketTickRecorder, TickSlot

START = datetime(2026, 9, 9, 14, 57, 0, tzinfo=timezone(timedelta(hours=8)))


def fixture_row():
    clock = [START]

    class Store:
        def append(self, row):
            return True

    def fetch(symbols):
        clock[0] += timedelta(seconds=2)  # Deterministic query latency.
        return {s: {"time": int(clock[0].timestamp() * 1000), "lastPrice": 1, "stockStatus": 18, "openInt": 18} for s in symbols}

    recorder = MarketTickRecorder(symbols=["510001.SH"], fetcher=fetch, store=Store(), now_fn=lambda: clock[0])
    rows = recorder.capture_slot(TickSlot(START, 0))
    return rows[0], clock[0]


class CaptureClockTests(unittest.TestCase):
    def test_observed_captured_at_precedes_fetch_completion(self):
        row, ended = fixture_row()
        self.assertEqual(datetime.fromisoformat(row["captured_at"]), START)
        self.assertEqual(datetime.fromisoformat(row["quote_time"]), ended)
        self.assertGreater(datetime.fromisoformat(row["quote_time"]), datetime.fromisoformat(row["captured_at"]))

    @unittest.expectedFailure
    def test_captured_at_can_be_used_as_price_contract_received_at(self):
        row, ended = fixture_row()
        self.assertGreaterEqual(datetime.fromisoformat(row["captured_at"]), ended)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(TOPIC):
        raise SystemExit("Output must be a new versioned ETF artifact")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CaptureClockTests))
    row, ended = fixture_row()
    payload = {"identity": "ETF-PHASE1-CAPTURE-CLOCK-L0-20260916-v1.0", "tests_run": result.testsRun, "passed": result.testsRun - len(result.expectedFailures) - len(result.failures) - len(result.errors), "retained_contract_failures": [{"test": test.id(), "assertion": trace.strip().splitlines()[-1]} for test, trace in result.expectedFailures], "errors": [test.id() for test, trace in result.errors], "failures": [test.id() for test, trace in result.failures], "unexpected_successes": [test.id() for test in result.unexpectedSuccesses], "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(), "fixture": {"logged_captured_at": row["captured_at"], "quote_time": row["quote_time"], "fetch_completed_at": ended.isoformat()}, "evidence_ceiling": "L0", "formal_backtests": 0}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
