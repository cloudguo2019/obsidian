"""Verify phase-3 signature and frozen design identity without running strategy."""

import argparse
import hashlib
import json
import re
from pathlib import Path


TOPIC = Path(__file__).resolve().parents[1]
ROOT = TOPIC.parents[2]
ENGINE = ROOT.parents[1] / "FINITUDE-1.4.2/sartre"
DRAFT = TOPIC / "experiments/ETF-REGIME-001/preregistration_draft_v1.0.json"
FROZEN = TOPIC / "experiments/ETF-REGIME-001/preregistration_v1.0.json"
REVIEW = TOPIC / "experiments/ETF-REGIME-001/PHASE3_PREREGISTRATION_REVIEW_v1.0.md"
SIGNATURE = TOPIC / "decisions/PHASE3_SIGNATURE_AND_CLOSURE_2026-09-25_v1.0.md"
DRAFT_MANIFEST = TOPIC / "decisions/PHASE3_MANIFEST_2026-09-18_v1.0.json"
MANIFEST = TOPIC / "decisions/PHASE3_FREEZE_MANIFEST_2026-09-25_v1.0.json"
USER_WORDS = "签署 v1.0，采用其中设计与新增门槛"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate():
    prior = read(DRAFT_MANIFEST)
    assert prior["status"] == "DRAFT_AWAITING_USER_SIGNATURE" and not prior["phase3_closed"]
    for rel, expected in prior["outputs"].items():
        assert digest(TOPIC / rel) == expected, ("draft_artifact_changed", rel)
    for rel, expected in prior["inputs"].items():
        assert digest(ROOT / rel) == expected, ("draft_source_changed", rel)
    for rel, expected in prior["engineering_hashes"].items():
        assert digest(ENGINE / rel) == expected, ("engineering_changed", rel)

    draft, frozen = read(DRAFT), read(FROZEN)
    assert frozen["identity"] == "ETF-PHASE3-PREREGISTRATION-20260925-v1.0"
    assert frozen["protocol_version"] == "1.0"
    assert frozen["status"] == "FROZEN_SIGNED" and frozen["phase3_closed"]
    assert frozen["source_draft_sha256"] == digest(DRAFT)
    assert frozen["source_draft_manifest_sha256"] == digest(DRAFT_MANIFEST)
    expected_metadata_changes = {"identity", "protocol_version", "status", "phase3_closed", "authorization"}
    assert set(frozen) - set(draft) == {"source_draft_sha256", "source_draft_manifest_sha256"}
    assert all(frozen[key] == value for key, value in draft.items()
               if key not in expected_metadata_changes), "substantive_design_changed"
    old_a, new_a = draft["authorization"], frozen["authorization"]
    assert set(old_a) == set(new_a)
    assert all(new_a[key] == value for key, value in old_a.items()
               if key not in {"user_instruction_this_turn", "signature", "signature_date"})
    assert new_a["signature"] == new_a["user_instruction_this_turn"] == USER_WORDS
    assert new_a["signature_date"] == "2026-09-25"
    assert not new_a["draft_signature_is_formal_batch_permission"]
    assert all(new_a[key] == 0 for key in ("formal_backtests", "lock_open", "simulation", "live"))
    assert frozen["empirical_evidence_ceiling"] == "L0"
    assert frozen["market_inventory_cutoff"] == "2026-09-09"
    assert frozen["experiment_accounting"]["account_scenario_cells_per_sample_batch"] == 35
    assert frozen["experiment_accounting"]["formal_runs_executed"] == 0
    binding = frozen["run_binding_requirements"]
    unresolved = [key for key, value in binding.items() if value is None]
    assert len(unresolved) == prior["run_binding_dependencies_unresolved"] == 15
    assert not frozen["sample_design_proposal"]["lock_exists"]
    assert not frozen["sample_design_proposal"]["actual_sample_identity_created"]
    closure = SIGNATURE.read_text(encoding="utf-8")
    assert USER_WORDS in closure and "接受并闭环" in closure
    assert digest(DRAFT) in closure and digest(FROZEN) in closure
    assert digest(REVIEW) in closure and digest(DRAFT_MANIFEST) in closure
    links_checked = 0
    for doc in (SIGNATURE, TOPIC / "README.md", TOPIC / "CG-ETF-ROTATION_MEMORY.md"):
        source = doc.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source):
            if link.startswith(("https://", "http://", "#")):
                continue
            target = (doc.parent / link.split("#")[0]).resolve()
            assert target.exists() or target == MANIFEST, ("broken_link", str(doc), link)
            links_checked += 1
    for index in (TOPIC / "README.md", TOPIC / "CG-ETF-ROTATION_MEMORY.md"):
        content = index.read_text(encoding="utf-8")
        assert "2026-09-25" in content and "阶段3" in content
        assert "PHASE3_SIGNATURE_AND_CLOSURE_2026-09-25_v1.0.md" in content
        assert "preregistration_v1.0.json" in content
    return {
        "identity": "ETF-PHASE3-FREEZE-MANIFEST-20260925-v1.0",
        "snapshot_date": "2026-09-25", "timezone": "Asia/Shanghai",
        "decision": "接受", "accepted_object": "Signed phase-3 design and new thresholds",
        "phase3_closed": True, "phase4_data_contract_drafting_permitted": True,
        "empirical_evidence_ceiling": "L0", "market_inventory_cutoff": "2026-09-09",
        "user_signature": USER_WORDS,
        "signed_draft_sha256": digest(DRAFT), "draft_manifest_sha256": digest(DRAFT_MANIFEST),
        "frozen_protocol_sha256": digest(FROZEN), "substantive_design_equal_to_signed_draft": True,
        "outputs": {path.relative_to(TOPIC).as_posix(): digest(path) for path in
                    (FROZEN, SIGNATURE, Path(__file__))},
        "inherited_draft_identity_counts": prior["identity_verification"],
        "registered_account_scenario_cells_per_sample_batch": 35,
        "run_binding_dependencies_unresolved": unresolved,
        "historical_diagnostic_dates_already_viewed": prior["diagnostic_dates_already_viewed"],
        "actual_sample_or_lock_identity_created": False,
        "new_strategy_tests": 0, "inherited_passed_L0": prior["inherited_passed_L0"],
        "local_links_checked": links_checked,
        "formal_results_read_this_turn": 0, "locked_results_opened_this_turn": 0,
        "new_sample_contamination_this_turn": False,
        "application_modified": False, "raw_data_modified": False,
        "historical_frozen_identities_modified": False,
        "authorizations": {key: new_a[key] for key in ("formal_backtests", "lock_open", "simulation", "live")},
        "actions_this_turn": {"formal_backtests": 0, "lock_open": 0, "simulation": 0, "live": 0},
        "next_work_gate": "Phase-4 data contract with PIT universe, prices, distributions, availability, costs, cash return, calendars and fills",
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
        assert read(MANIFEST) == payload, "phase3_freeze_manifest_changed"
    print(json.dumps({key: payload[key] for key in (
        "identity", "decision", "phase3_closed", "substantive_design_equal_to_signed_draft",
        "registered_account_scenario_cells_per_sample_batch", "run_binding_dependencies_unresolved",
        "authorizations")}, ensure_ascii=False))
