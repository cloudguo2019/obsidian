"""Authenticate a draft protocol; never run strategy or read performance.

Default: read-only verification. --create: exclusively create the draft manifest.
All identity files are separate from mutable project indexes and run results.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from validate_phase1_closure_v1 import validate as validate_phase1

TOPIC = Path(__file__).resolve().parents[1]
ROOT = TOPIC.parents[2]
ENGINE = ROOT.parents[1] / "FINITUDE-1.4.2/sartre"
PREREG = TOPIC / "experiments/ETF-REGIME-001/preregistration_draft_v1.0.json"
MANIFEST = TOPIC / "decisions/PHASE3_MANIFEST_2026-09-18_v1.0.json"
SKILL = Path.home() / ".codex/skills/cg-etf-rotation/SKILL.md"
PROTOCOL = SKILL.parent / "references/research-protocol.md"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def validate():
    p = read(PREREG)
    assert p["status"] == "DRAFT_AWAITING_USER_SIGNATURE"
    assert p["phase"] == 3 and not p["phase3_closed"]
    assert p["empirical_evidence_ceiling"] == "L0"
    a = p["authorization"]
    assert a["signature"] is None and a["signature_date"] is None
    assert a["drafting_authorized"] and not a["draft_signature_is_formal_batch_permission"]
    for name in ("formal_backtests", "lock_open", "simulation", "live"):
        assert a[name] == 0

    pc = p["primary_comparison"]
    assert pc["candidate"] == "ETF-REGIME-001"
    assert pc["control"] == "ETF-BASE-001-CS78"
    assert pc["economic_threshold_absolute"] == 0.10
    assert pc["confidence_level"] == 0.95
    arms = p["arms"]
    ids = {arm["id"] for arm in arms}
    assert len(ids) == len(arms) == p["experiment_accounting"]["base_accounts"] == 5
    assert {pc["candidate"], pc["control"], pc["original_control_also_reported"]} <= ids
    assert p["experiment_accounting"]["confirmatory_primary_hypotheses"] == 1
    assert p["experiment_accounting"]["candidate_hypotheses"] == 2
    assert len(p["scenarios"]) == 7
    assert len({s["id"] for s in p["scenarios"]}) == 7
    assert 5 * 7 == p["experiment_accounting"]["account_scenario_cells_per_sample_batch"]
    assert p["experiment_accounting"]["formal_runs_executed"] == 0
    assert p["experiment_accounting"]["development_matching_searches"] == 0
    assert p["experiment_accounting"]["macd_parameter_searches"] == 0
    r = p["inherited_rules"]
    assert r["initial_cash_cny"] == r["execution_asset_cap_cny"] == 5000
    assert r["max_positions"] == 3 and r["symbol_target_weight"] == 0.20
    assert r["symbol_max_weight"] == 0.20 and r["portfolio_max_weight"] == 0.60
    assert r["buy_rank_top_n"] == 5 and r["hold_rank_top_n"] == 15
    assert not r["rank_fill_outside_top5"] and r["rank_before_trend_filter"]
    assert r["accepted_clock_limitations"] == [2, 5]
    assert not r["captured_at_is_received_at"]
    assert not r["complete_close_may_be_backfilled_to_1457"]
    m = p["indicator_construction"]["macd"]
    assert (m["fast"], m["slow"], m["signal"]) == (12, 26, 9)
    assert not m["ewm_adjust"]
    for arm in arms:
        assert arm["warmup_bars"] == (61 if arm["id"].endswith("ORIG61") else 78)
    ex = p["exposure_comparison"]
    assert ex["method"] == "natural_actual_account_exposure_gate_no_rescaling"
    assert not ex["current_draft_changes_target_weights"]
    assert (ex["mean_difference_max_absolute"], ex["peak_difference_max_absolute"]) == (0.02, 0.03)
    rules = p["decision_rule_order"]
    assert [x["decision"] for x in rules] == ["修改", "观察", "淘汰", "接受", "观察"]
    binding = p["run_binding_requirements"]
    required = ["research_implementation_hash", "research_config_hash", "universe_event_manifest",
        "clean_data_manifest", "data_contract_version", "sample_split_manifest", "lock_manifest",
        "exchange_product_calendar_manifest", "actual_cost_model", "cash_yield_model",
        "auction_fill_and_queue_contract", "execution_reconciliation_report",
        "baseline_acceptance_manifest", "exact_batch_authorization", "result_paths_and_expected_cell_ledger"]
    assert all(binding[key] is None for key in required)
    sample = p["sample_design_proposal"]
    assert not sample["actual_sample_identity_created"] and not sample["lock_exists"]
    assert not sample["archival_holdout_is_final_untouched_lock"]
    assert not sample["final_lock_peeking_and_extension_on_performance"]
    plan_path = TOPIC / "datasets/PHASE1_READONLY_PLAN_v1.0_2026-09-16.json"
    assert sample["diagnostic_dates_already_viewed"] == read(plan_path)["dates"]
    assert len(sample["rolling_historical_oos_folds"]) == 4
    ordered = [sample["development"], sample["validation"]] + sample["rolling_historical_oos_folds"] + [sample["archival_reserved_holdout"]]
    assert all(start <= end for start, end in ordered)
    assert all(a[1] < b[0] for a, b in zip(ordered, ordered[1:]))
    uncertainty = p["uncertainty"]
    assert uncertainty["same_indices_for_all_arms"]
    assert uncertainty["replicates_per_block_length"] == 10000
    assert uncertainty["mean_block_sessions_primary"] == 20
    assert uncertainty["mean_block_sessions_sensitivity"] == [10, 40]

    prior = validate_phase1()
    assert read(TOPIC / "decisions/PHASE1_CLOSURE_MANIFEST_2026-09-17_v1.0.json") == prior
    p2_path = TOPIC / "decisions/PHASE2_MANIFEST_2026-09-17_v1.0.json"
    p2 = read(p2_path)
    verified = 0
    for collection in ("local_inputs", "outputs"):
        for rel, sha in p2[collection].items():
            assert digest(TOPIC / rel) == sha, ("phase2_identity_changed", rel)
            verified += 1
    for rel, sha in p["authority"]["engineering_hashes"].items():
        assert digest(ENGINE / rel) == sha, ("engineering_changed", rel)
    assert all((TOPIC / p["authority"][key]).exists() for key in (
        "charter", "phase1_baseline", "price_contract", "execution_repairs", "theory", "phase2_closure"))

    outputs = [PREREG, Path(__file__),
        TOPIC / "experiments/ETF-REGIME-001/PHASE3_PREREGISTRATION_REVIEW_v1.0.md",
        TOPIC / "decisions/PHASE3_REVIEW_2026-09-18_v1.0.md"]
    indexes = [TOPIC / "README.md", TOPIC / "CG-ETF-ROTATION_MEMORY.md"]
    links = 0
    for doc in [x for x in outputs if x.suffix == ".md"] + indexes:
        source = doc.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source):
            if link.startswith(("https://", "http://", "#")):
                continue
            target = (doc.parent / link.split("#")[0]).resolve()
            assert target.exists() or target == MANIFEST, ("broken_link", str(doc), link)
            links += 1
    for doc in indexes:
        source = doc.read_text(encoding="utf-8")
        assert "阶段3" in source and "待签署" in source, ("stale_index", str(doc))
        assert "PHASE3_PREREGISTRATION_REVIEW_v1.0.md" in source
    sources = [ROOT / "PERSONAL_STRATEGY_RESEARCH_FRAMEWORK.md", p2_path, plan_path,
        TOPIC / "decisions/PHASE1_CLOSURE_MANIFEST_2026-09-17_v1.0.json"]
    sources += [TOPIC / p["authority"][key] for key in (
        "charter", "phase1_baseline", "price_contract", "execution_repairs", "theory", "phase2_closure")]
    return {
        "identity": "ETF-PHASE3-DRAFT-MANIFEST-20260918-v1.0",
        "snapshot_date": "2026-09-18", "timezone": "Asia/Shanghai",
        "status": p["status"], "phase3_closed": False, "draft_structure_validated": True,
        "draft_choices_adopted": False, "empirical_evidence_ceiling": "L0",
        "market_inventory_cutoff": p["market_inventory_cutoff"],
        "user_instruction": a["user_instruction_this_turn"],
        "single_next_gate": "User signs the exact phase3 draft v1.0 before any freeze",
        "outputs": {path.relative_to(TOPIC).as_posix(): digest(path) for path in outputs},
        "inputs": {path.relative_to(ROOT).as_posix(): digest(path) for path in sources},
        "skill": {"path": SKILL.as_posix(), "sha256": digest(SKILL)},
        "skill_protocol": {"path": PROTOCOL.as_posix(), "sha256": digest(PROTOCOL)},
        "engineering_hashes": p["authority"]["engineering_hashes"],
        "identity_verification": {"phase1_raw_inputs": prior["raw_inputs_hashes_reverified"],
            "phase1_engineering_sources": prior["engineering_sources_reverified"],
            "phase2_local_artifacts": verified},
        "local_links_checked": links,
        "draft_accounts": 5, "draft_candidates": 2, "draft_primary_hypotheses": 1,
        "draft_scenarios": 7, "draft_cells_per_sample_batch": 35,
        "run_binding_dependencies_unresolved": len(required),
        "actual_sample_or_lock_identity_created": False,
        "diagnostic_dates_already_viewed": sample["diagnostic_dates_already_viewed"],
        "new_strategy_tests": 0, "inherited_passed_L0": 68,
        "formal_results_read_this_turn": 0, "locked_results_opened_this_turn": 0,
        "new_sample_contamination_this_turn": False,
        "application_modified": False, "raw_data_modified": False,
        "historical_frozen_identities_modified": False,
        "authorizations": {key: a[key] for key in ("formal_backtests", "lock_open", "simulation", "live")},
        "actions_this_turn": {"formal_backtests": 0, "lock_open": 0, "simulation": 0, "live": 0},
        "external_method_source": {"url": uncertainty["external_method_source"],
            "read_scope": uncertainty["source_read_scope"], "evidence_grade": "B"},
        "mutable_indexes_excluded": ["README.md", "CG-ETF-ROTATION_MEMORY.md"]
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
        assert read(MANIFEST) == payload, "phase3_draft_manifest_changed"
    print(json.dumps({key: payload[key] for key in (
        "identity", "status", "phase3_closed", "draft_structure_validated",
        "draft_cells_per_sample_batch", "run_binding_dependencies_unresolved",
        "identity_verification", "local_links_checked", "authorizations")}, ensure_ascii=False))
