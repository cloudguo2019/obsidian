"""Identity-only verification. Does not rerun tests or invoke the broker/SDK.

--create writes the new manifest once; default verifies it without mutation.
Historic and new artifacts are checked separately rather than rewriting counts.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

TOPIC = Path(__file__).resolve().parents[1]
ROOT = TOPIC.parents[2]
ENGINE = ROOT.parents[1] / "FINITUDE-1.4.2/sartre"
MANIFEST = TOPIC / "decisions/PHASE1_THREE_REPAIRS_MANIFEST_2026-09-17_v1.0.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read(rel):
    return json.loads((TOPIC / rel).read_text(encoding="utf-8"))


def validate():
    historic_path = TOPIC / "decisions/PHASE1_EVIDENCE_MANIFEST_v1.0_2026-09-16.json"
    historic = json.loads(historic_path.read_text(encoding="utf-8"))
    for collection in ("artifacts", "frozen_protocol_identities"):
        for rel, sha in historic[collection].items():
            assert digest(ROOT / rel) == sha, ("historic_artifact_changed", rel)
    audit = read("datasets/PHASE1_READONLY_AUDIT_v1.0_2026-09-16.json")
    for rel, sha in audit["engineering_hashes"].items():
        assert digest(ENGINE / rel) == sha, ("engineering_snapshot_changed", rel)
    for item in audit["inputs"]:
        assert digest(ROOT / item["path"]) == item["sha256"], ("raw_input_changed", item["path"])
    result = read("decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt2.json")
    assert result["tests_run"] == result["passed"] == len(result["passed_tests"]) == 39
    assert not result["failures"] and not result["errors"] and result["expected_failures"] == 0
    assert result["three_repair_gate_passed"] and not result["phase1_gate_passed"]
    assert not result["application_modified"] and result["evidence_ceiling"] == "L0"
    for name in ("formal_backtests", "locked_results_opened", "simulation_authorizations", "live_trading_authorizations"):
        assert result[name] == 0
    for item in result["sources"]:
        assert digest(TOPIC / item["path"]) == item["sha256"], item["path"]
        compile((TOPIC / item["path"]).read_text(encoding="utf-8"), item["path"], "exec")
    first = read("decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt1.json")
    archive = read("decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt1_sources.json")
    assert first["tests_run"] == 39 and first["passed"] == 31
    assert len(first["errors"]) == 7 and len(first["failures"]) == 1
    assert [{k: v for k, v in item.items() if k != "text"} for item in archive["sources"]] == first["sources"]
    for item in archive["sources"]:
        compile(item["text"], item["path"], "exec")
        # Archive is text; unchanged CRLF originals can be authenticated against
        # original bytes plus normalized text. Modified test source was LF.
        normalized_sha = hashlib.sha256(item["text"].encode("utf-8")).hexdigest().upper()
        if normalized_sha != item["sha256"]:
            source = TOPIC / item["path"]
            assert digest(source) == item["sha256"]
            assert source.read_text(encoding="utf-8") == item["text"]
    # The implementation did not change while the failing fixtures were fixed.
    for item in first["sources"]:
        if item["path"].startswith("baselines/"):
            assert digest(TOPIC / item["path"]) == item["sha256"]
    docs = [TOPIC / rel for rel in (
        "baselines/ETF-EXECUTION-REPAIRS-001_v1.0.md",
        "decisions/PHASE1_THREE_REPAIRS_ACCEPTANCE_2026-09-17_v1.0.md")]
    links = 0
    for path in docs:
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = (path.parent / link.split("#")[0]).resolve()
            assert target.exists() or target == MANIFEST, ("missing_link", str(path), link)
            links += 1
    artifacts = docs + [TOPIC / item["path"] for item in result["sources"]] + [
        TOPIC / "decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt1.json",
        TOPIC / "decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt1_sources.json",
        TOPIC / "decisions/PHASE1_THREE_REPAIRS_L0_v1.0_2026-09-17_attempt2.json",
        Path(__file__)]
    return {"identity": "ETF-PHASE1-THREE-REPAIRS-MANIFEST-20260917-v1.0",
        "artifacts": {p.relative_to(TOPIC).as_posix(): digest(p) for p in artifacts},
        "historic_manifest_sha256": digest(historic_path),
        "historic_artifacts_and_protocols_verified": len(historic["artifacts"]) + len(historic["frozen_protocol_identities"]),
        "raw_inputs_verified": len(audit["inputs"]),
        "engineering_sources_verified": len(audit["engineering_hashes"]),
        "engineering_hashes": audit["engineering_hashes"], "local_links_verified": links,
        "repair_checks": {"tests": 39, "passed": 39, "expected_failures": 0},
        "legacy_regression_observed_from_completed_commands": {
            "engine_tests": 17, "engine_passed": 17, "price_tests": 12, "price_passed": 12,
            "note": "Passed in this repair turn; identity validator does not repeat the tests",
            "source_hashes": {p: digest(TOPIC / p) for p in (
                "tests/run_etf_base_001_l0.py", "tests/test_etf_price_contract_v1.py")}},
        "scope": "Isolated research guard/ledger and offline legacy pipeline bridge; synthetic costs/rules/calendars",
        "three_repair_gate_passed": True, "phase1_gate_passed": False,
        "remaining_clock_contract_failures": 2, "evidence_ceiling": "L0",
        "authorizations": {"formal_backtests": 0, "lock_open": 0, "simulation": 0, "live": 0}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    payload = validate()
    if args.create:
        with MANIFEST.open("x", encoding="utf-8") as out:
            out.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        assert json.loads(MANIFEST.read_text(encoding="utf-8")) == payload, "manifest_identity_mismatch"
    print(json.dumps({k: payload[k] for k in (
        "identity", "raw_inputs_verified", "engineering_sources_verified", "repair_checks",
        "three_repair_gate_passed", "phase1_gate_passed", "remaining_clock_contract_failures")}, ensure_ascii=False))
