"""Verify bounded phase-1 evidence identities and preserve the failed gates."""
import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from audit_phase1_readonly_v1 import ROOT, TOPIC, ENGINE, digest


def validate():
    audit_path = TOPIC / "datasets/PHASE1_READONLY_AUDIT_v1.0_2026-09-16.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    for item in audit["inputs"]:
        assert digest(ROOT / item["path"]) == item["sha256"], item["path"]
    for rel, expected in audit["engineering_hashes"].items():
        assert digest(ENGINE / rel) == expected, rel
    expected_core = {
        "sartre_core/strategies/etf_rotation_core.py": "1F7006FC7240157840E928DD6EE1DFDC50868331F26A16506A31A1EE38884317",
        "sartre_core/strategies/macd_core.py": "C2199714C1DD3C848F72E6E05A67BB8F1788C8442AC5188CCBCFC4E84E8155E7",
        "sartre_core/config/etf_rotation_config.json": "8E14BC5BFEA0429158740E93308A6261BD2530429B4B697D8683770E2F6F355D",
    }
    assert all(audit["engineering_hashes"][p] == h for p, h in expected_core.items())
    results = [
        ("decisions/PHASE1_EXECUTION_L0_v1.0_2026-09-16_attempt1.json", "tests/run_phase1_execution_l0_v1.py", 15, 11, 4),
        ("decisions/PHASE1_CAPTURE_CLOCK_L0_v1.0_2026-09-16.json", "tests/run_phase1_capture_clock_l0_v1.py", 2, 1, 1),
    ]
    for rel, source, count, passed, gaps in results:
        item = json.loads((TOPIC / rel).read_text(encoding="utf-8"))
        assert item["tests_run"] == count and item["passed"] == passed
        assert len(item["retained_contract_failures"]) == gaps
        assert not item.get("errors") and not item.get("failures") and not item.get("unexpected_failures") and not item.get("unexpected_successes")
        assert item["script_sha256"] == digest(TOPIC / source)
    clock = json.loads((TOPIC / "datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.1_2026-09-16.json").read_text(encoding="utf-8"))
    assert clock["source_files_equal"] and clock["input_hashes_revalidated"] == 51
    assert digest(ENGINE / "sartre_core/data/market_tick.py") == clock["tick_source_sha256"]
    assert digest(ENGINE / "sartre_core/engine/runtime_logger.py") == clock["logger_sha256"]
    assert audit["totals"]["broker_fill_rows"] == 0
    # Replay only the deterministic numerical counterexample, with no SDK.
    fixture_path = TOPIC / "tests/run_phase1_execution_l0_v1.py"
    spec = importlib.util.spec_from_file_location("etf_phase1_offline_fixture", fixture_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fixture = module.PipelineFixture()
    fixture._run_closing_auction_pipeline()
    broker = fixture.xt_trader
    measured = {"positive_symbols": len([v for v in broker.volumes.values() if v > 0]), "cash": broker.cash, "unadjusted_market_value": sum(broker.volumes.values()), "equity": broker.asset, "exposure": sum(broker.volumes.values()) / broker.asset, "orders": broker.orders, "scope": "offline synthetic broker fixture; not archived actual trades"}
    assert measured["positive_symbols"] == 4 and measured["unadjusted_market_value"] == 3900 and abs(measured["equity"] - 4999.9) < 1e-8
    files = [p for folder in ["scripts", "tests"] for p in (TOPIC / folder).glob("*phase1*v1.py")]
    for path in files:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    docs = [TOPIC / p for p in ["baselines/ETF-BASE-001_SPEC_v0.3.md", "baselines/ETF-BASE-001_EXECUTION_CONTRACT_DRAFT_v0.4.md", "decisions/PHASE1_REVIEW_2026-09-16_v1.0.md"]]
    checked_links = 0
    for doc in docs:
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
            if link.startswith("https://"):
                continue
            assert (doc.parent / link.split("#")[0]).resolve().exists(), (doc, link)
            checked_links += 1
    artifacts = docs + [TOPIC / p[0] for p in results] + [audit_path, TOPIC / "datasets/PHASE1_READONLY_PLAN_v1.0_2026-09-16.json", TOPIC / "datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.0_2026-09-16.json", TOPIC / "datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.1_2026-09-16.json"] + files
    protocols = [TOPIC / "hypotheses/research_charter_v1.2.md", TOPIC / "baselines/ETF-PRICE-001_CONTRACT_v1.0.md"]
    return {"identity": "ETF-PHASE1-EVIDENCE-MANIFEST-20260916-v1.0", "validated_at_utc": datetime.now(timezone.utc).isoformat(), "validation_script_sha256": digest(Path(__file__)), "raw_inputs_hashes_verified": len(audit["inputs"]), "engineering_hashes_verified": len(audit["engineering_hashes"]), "linked_local_artifacts_verified": checked_links, "python_sources_compiled_without_writing": len(files), "artifacts": {p.relative_to(ROOT).as_posix(): digest(p) for p in artifacts}, "frozen_protocol_identities": {p.relative_to(ROOT).as_posix(): digest(p) for p in protocols}, "legacy_regression_observed_in_this_turn": {"engineering_passed": 17, "price_passed": 12, "source_hashes": {p: digest(TOPIC / p) for p in ["tests/run_etf_base_001_l0.py", "tests/test_etf_price_contract_v1.py"]}}, "combined_l0": {"checks": 46, "passed": 41, "retained_contract_failures": 5, "unexplained_errors": 0}, "synthetic_counterexample": measured, "phase1_gate_passed": False, "decision": "修改", "evidence_ceiling": "L0", "authorizations": {"formal_backtests": 0, "lock_open": 0, "simulation": 0, "live": 0}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(TOPIC):
        raise SystemExit("Output must be a new versioned ETF artifact")
    result = validate()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": out.as_posix(), "raw_inputs_verified": result["raw_inputs_hashes_verified"], "engineering_verified": result["engineering_hashes_verified"], "combined_l0": result["combined_l0"], "counterexample": result["synthetic_counterexample"], "phase1_gate_passed": False}, ensure_ascii=False))
