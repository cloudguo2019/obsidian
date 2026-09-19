"""Verify phase-1 closure identity without rerunning tests or querying APIs.

Historical failed tests remain failed. Two clock acceptance exceptions and
three research repairs are recorded separately from the phase gate decision.
"""
import argparse
import json
import re
from pathlib import Path

from validate_phase1_repairs_v1 import TOPIC, digest, validate as validate_repairs

MANIFEST = TOPIC / "decisions/PHASE1_CLOSURE_MANIFEST_2026-09-17_v1.0.json"
BASELINE = TOPIC / "baselines/ETF-BASE-001_PHASE1_BASELINE_v1.0.md"
CLOSURE = TOPIC / "decisions/PHASE1_CLOSURE_2026-09-17_v1.0.md"
INSTRUCTION = "第二项和第五项中的时间可以忽略，因为我使用的是tick数据，3秒一个快照，同时策略是日线策略，这点不影响。把阶段1闭环"


def read(rel):
    return json.loads((TOPIC / rel).read_text(encoding="utf-8"))


def validate():
    repairs = validate_repairs()
    prior_path = TOPIC / "decisions/PHASE1_THREE_REPAIRS_MANIFEST_2026-09-17_v1.0.json"
    assert read(prior_path.relative_to(TOPIC)) == repairs, "prior_repair_manifest_changed"
    execution = read("decisions/PHASE1_EXECUTION_L0_v1.0_2026-09-16_attempt1.json")
    clock = read("decisions/PHASE1_CAPTURE_CLOCK_L0_v1.0_2026-09-16.json")
    assert len(execution["retained_contract_failures"]) == 4
    assert len(clock["retained_contract_failures"]) == 1

    def case(fragment):
        found = [t for t in execution["retained_contract_failures"] if fragment in t]
        assert len(found) == 1, fragment
        return found[0]

    dispositions = [
        {"original_item": 1, "test": case("full_account"), "status": "repaired_in_research_L0"},
        {"original_item": 2, "test": case("future_quote"), "status": "accepted_limitation_for_phase1"},
        {"original_item": 3, "test": case("commission"), "status": "repaired_in_research_L0"},
        {"original_item": 4, "test": case("nontrading_calendar_day"), "status": "repaired_in_research_L0"},
        {"original_item": 5, "test": clock["retained_contract_failures"][0]["test"], "status": "accepted_limitation_for_phase1"},
    ]
    assert {d["test"] for d in dispositions} == set(execution["retained_contract_failures"] +
        [item["test"] for item in clock["retained_contract_failures"]])
    for doc in (BASELINE, CLOSURE):
        source = doc.read_text(encoding="utf-8")
        assert INSTRUCTION in source, "missing_exact_user_acceptance"
        assert "L0" in source and "阶段1" in source and "闭环" in source
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source):
            target = (doc.parent / link.split("#")[0]).resolve()
            assert target.exists() or target == MANIFEST, ("missing_local_link", link)
    # Verify mutable project indexes reflect the new gate; do not freeze them
    # into this manifest because later material turns must update the indexes.
    for rel in ("CG-ETF-ROTATION_MEMORY.md", "README.md"):
        index = (TOPIC / rel).read_text(encoding="utf-8")
        assert "阶段1已闭环" in index, ("stale_project_index", rel)
        assert "PHASE1_CLOSURE_2026-09-17_v1.0.md" in index
    sources = [BASELINE, CLOSURE, Path(__file__), prior_path] + [TOPIC / rel for rel in (
        "hypotheses/research_charter_v1.2.md",
        "baselines/ETF-PRICE-001_CONTRACT_v1.0.md",
        "baselines/ETF-BASE-001_SPEC.md",
        "baselines/ETF-BASE-001_SPEC_v0.2.md",
        "baselines/ETF-BASE-001_SPEC_v0.3.md",
        "baselines/ETF-EXECUTION-REPAIRS-001_v1.0.md",
        "datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.1_2026-09-16.json",
        "decisions/PHASE1_EXECUTION_L0_v1.0_2026-09-16_attempt1.json",
        "decisions/PHASE1_CAPTURE_CLOCK_L0_v1.0_2026-09-16.json",
        "decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt2.json")]
    return {
        "identity": "ETF-PHASE1-CLOSURE-20260917-v1.0",
        "decision": "接受", "phase1_gate_passed": True, "phase1_closed": True,
        "accepted_object": "Research engineering formalization with two user-accepted clock limitations",
        "evidence_ceiling": "L0", "data_cutoff": "2026-09-09",
        "user_instruction": INSTRUCTION, "user_stated_tick_snapshot_seconds": 3,
        "original_code_future_quote_tolerance_seconds_unchanged": 5,
        "clock_impact_empirically_verified": False,
        "historical_failures_preserved": 5, "dispositions": dispositions,
        "repaired_in_research_L0": 3, "clock_limitations_accepted_for_phase1": 2,
        "blocking_items_within_adopted_phase1_scope": 0,
        "latest_completed_l0_tests": {"engine": 17, "price": 12, "repairs": 39, "passed": 68,
            "note": "Inherited completed runs authenticated by prior manifests; no test reruns in this closure turn"},
        "raw_inputs_hashes_reverified": repairs["raw_inputs_verified"],
        "engineering_sources_reverified": repairs["engineering_sources_verified"],
        "sources": {p.relative_to(TOPIC).as_posix(): digest(p) for p in sources},
        "deferred_dependencies": ["PIT universe", "provider front_ratio/factor reconciliation",
            "long-history raw prices and distributions", "actual broker fees/product rules/calendars",
            "complete broker and pending-order state", "formal implementation and economic fill model"],
        "deferred_gate": "Phase 4-5 data contract/audit and before any formal experiment",
        "phase2_permitted": True, "phase2_started": False,
        "next_work": "Phase 2 theory, alternative explanations and falsification conditions",
        "implementation_changed_in_closure_turn": False, "application_modified": False,
        "authorizations": {"formal_backtests": 0, "lock_open": 0, "simulation": 0, "live": 0},
        "locked_results_opened": 0, "formal_sample_contamination": False,
        "closure_validator_first_attempt": "TypeError from treating the prior clock failure record object as a test-id string; parser corrected before manifest creation; no strategy/data/test change",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    payload = validate()
    if args.create:
        with MANIFEST.open("x", encoding="utf-8") as out:
            out.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        assert json.loads(MANIFEST.read_text(encoding="utf-8")) == payload, "closure_manifest_changed"
    print(json.dumps({k: payload[k] for k in (
        "identity", "decision", "phase1_closed", "evidence_ceiling", "repaired_in_research_L0",
        "clock_limitations_accepted_for_phase1", "raw_inputs_hashes_reverified",
        "engineering_sources_reverified", "phase2_permitted", "authorizations")}, ensure_ascii=False))
