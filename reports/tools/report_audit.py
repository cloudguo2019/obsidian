#!/usr/bin/env python3
"""Sample and verify numerical facts embedded in a Markdown research report.

Audit markers use one JSON object per HTML comment, for example:
<!-- AUDIT {"field":"2025 revenue","reported":"1644085465.86","unit":"CNY","source1":"annual report","source2":"prospectus"} -->
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from decimal import Decimal, getcontext
from pathlib import Path


getcontext().prec = 40
PATTERN = re.compile(r"<!--\s*AUDIT\s+(\{.*?\})\s*-->")


def parse_markers(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    markers = [json.loads(match.group(1)) for match in PATTERN.finditer(text)]
    if not markers:
        raise SystemExit("No AUDIT markers found")
    return markers


def pct_gap(a: Decimal, b: Decimal) -> Decimal:
    base = max(abs(a), abs(b))
    return Decimal(0) if base == 0 else abs(a - b) / base * 100


def extract(args: argparse.Namespace) -> None:
    markers = parse_markers(Path(args.report))
    count = max(1, math.ceil(len(markers) * float(args.sample_pct) / 100))
    sample = random.Random(args.seed).sample(markers, count)
    print(json.dumps({
        "report": str(Path(args.report).resolve()),
        "population": len(markers),
        "sample_pct": float(args.sample_pct),
        "sample_size": count,
        "seed": args.seed,
        "sample": sample,
    }, ensure_ascii=False, indent=2))


def verdict(args: argparse.Namespace) -> None:
    markers = {m["field"]: m for m in parse_markers(Path(args.report))}
    results_text = Path(args.results).read_text(encoding="utf-8") if Path(args.results).exists() else args.results
    results = json.loads(results_text)
    rows = results.get("results", results)
    tolerance = Decimal(str(args.tolerance_pct))
    checks = []
    overall = True
    for row in rows:
        field = row["field"]
        if field not in markers:
            checks.append({"field": field, "status": "FAIL", "reason": "field absent from report markers"})
            overall = False
            continue
        reported = Decimal(str(markers[field]["reported"]))
        observed = [Decimal(str(v)) for v in row["observed"]]
        if len(observed) < 2:
            checks.append({"field": field, "status": "FAIL", "reason": "fewer than two source observations"})
            overall = False
            continue
        gaps = [pct_gap(reported, value) for value in observed]
        source_gap = pct_gap(max(observed), min(observed))
        passed = max(gaps + [source_gap]) <= tolerance
        overall = overall and passed
        checks.append({
            "field": field,
            "reported": str(reported),
            "observed": [str(v) for v in observed],
            "reported_to_source_gap_pct": [str(g.quantize(Decimal("0.000001"))) for g in gaps],
            "source_pair_gap_pct": str(source_gap.quantize(Decimal("0.000001"))),
            "status": "PASS" if passed else "FAIL",
        })
    print(json.dumps({
        "verdict": "PASS" if overall else "FAIL",
        "tolerance_pct": str(tolerance),
        "checks": checks,
    }, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    x = sub.add_parser("extract")
    x.add_argument("--report", required=True)
    x.add_argument("--sample-pct", default="15")
    x.add_argument("--seed", type=int, default=20260718)
    x.set_defaults(func=extract)
    x = sub.add_parser("verdict")
    x.add_argument("--report", required=True)
    x.add_argument("--results", required=True, help="JSON file path or inline JSON")
    x.add_argument("--tolerance-pct", default="1")
    x.set_defaults(func=verdict)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
