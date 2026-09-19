"""Versioned correction: captured_at is a request-start time, not receipt."""
import argparse
import json
from pathlib import Path

from refine_phase1_timestamps_v1 import refine
from audit_phase1_readonly_v1 import ROOT, TOPIC, DATA, ENGINE, digest


def finalize():
    result = refine()
    parent = TOPIC / "datasets/PHASE1_TIMESTAMP_AMENDMENT_v1.0_2026-09-16.json"
    engine_tick = ENGINE / "sartre_core/data/market_tick.py"
    archived_tick = DATA / "data/market_tick.py"
    code = engine_tick.read_text(encoding="utf-8")
    section = code[code.index("    def capture_slot("):code.index("    def _wait_until(")]
    assert section.index("captured_at =") < section.index("self._fetch()")
    assert "self.capture_slot(slot, captured_at=now, symbols=owned)" in code
    result.update({
        "identity": "ETF-PHASE1-TIMESTAMP-AMENDMENT-20260916-v1.1",
        "supersedes_clock_interpretation": parent.relative_to(ROOT).as_posix(),
        "superseded_sha256": digest(parent), "script_sha256": digest(Path(__file__)),
        "tick_source_sha256": digest(engine_tick), "archived_tick_source_sha256": digest(archived_tick),
        "source_files_equal": digest(engine_tick) == digest(archived_tick),
        "interpretation": [
            "Verified capture_slot records captured_at before _fetch(); _run_session supplies its pre-query now. It is a polling request-start marker, not a post-query receipt timestamp.",
            "A vendor quote after captured_at may arrive normally during query latency. The synthetic two-second-latency L0 fixture proves this possibility without clock skew or future market access.",
            "The closing-auction pipeline also samples now once before its sequential loop. event_time therefore predates later per-symbol query completions and is truncated to seconds.",
            "261/516 execution quotes lead logged event_time by one to three seconds; 285/1440 selected pre-15:00 quotes lead polling-start captured_at. These are incompatible clock-field semantics, not proven future-information leakage.",
            "Existing captured_at cannot be substituted into ETF-PRICE-001 ProxyTick.received_at, and first_usable_capture_time in the parent audit is only a start-marker diagnostic, not validated decision cutoff tau.",
            "A new request_started_at, received_at after query return, quote_at, target_generated_at and submission/acknowledgement clock contract is required; old fields must not be relabeled or repaired by inventing receive times.",
            "285/1440 is specific to the unchanged three-symbol eight-date case-study sample; it is not a rate estimated for the whole ETF universe.",
            "Stale flags over 14:57-15:30 include post-close repeats; the pre-15:00 sample has 356/1440 stale flags, including repeated quotes, which do not automatically prove unusable lastPrice.",
        ],
    })
    config_path = ENGINE / "sartre_core/config/base_config.json"
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    result["base_config_sha256"] = digest(config_path)
    result["configured_sdk_path_checks"] = [{"name": item.get("name", "base"), "sdk_root": Path(item["xtquant_site_packages"]).as_posix(), "root_exists": Path(item["xtquant_site_packages"]).exists(), "xtdata_source_exists": (Path(item["xtquant_site_packages"]) / "xtquant/xtdata.py").exists()} for item in [cfg["qmt"], *cfg["qmt_path_options"]]]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(TOPIC):
        raise SystemExit("Output must be a new versioned ETF artifact")
    result = finalize()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": out.as_posix(), "captured_at_semantics": "pre-query request start", "source_files_equal": result["source_files_equal"], "sdk_roots_found": sum(r["root_exists"] for r in result["configured_sdk_path_checks"])}, ensure_ascii=False))
