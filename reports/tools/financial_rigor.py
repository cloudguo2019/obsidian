#!/usr/bin/env python3
"""Deterministic, Decimal-based checks for investment research reports."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any


getcontext().prec = 40


def d(value: Any) -> Decimal:
    return Decimal(str(value))


def q(value: Decimal, places: str = "0.0001") -> str:
    return format(value.quantize(Decimal(places)), "f")


def pct_gap(a: Decimal, b: Decimal) -> Decimal:
    base = max(abs(a), abs(b))
    return Decimal(0) if base == 0 else abs(a - b) / base * 100


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def load_json(value: str) -> Any:
    """Load inline JSON, or a UTF-8 JSON file when prefixed with @."""
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    return json.loads(value)


def verify_market_cap(args: argparse.Namespace) -> None:
    price, shares, reported = d(args.price), d(args.shares), d(args.reported)
    calculated = price * shares
    gap = pct_gap(calculated, reported)
    emit({
        "command": "verify-market-cap",
        "currency": args.currency,
        "price": str(price),
        "shares": str(shares),
        "calculated_market_cap": q(calculated, "0.01"),
        "reported_market_cap": str(reported),
        "gap_pct": q(gap, "0.000001"),
        "tolerance_pct": str(args.tolerance_pct),
        "status": "PASS" if gap <= d(args.tolerance_pct) else "FAIL",
    })


def cross_validate(args: argparse.Namespace) -> None:
    raw = load_json(args.values)
    values = {name: d(value) for name, value in raw.items()}
    hi, lo = max(values.values()), min(values.values())
    gap = pct_gap(hi, lo)
    emit({
        "command": "cross-validate",
        "field": args.field,
        "unit": args.unit,
        "values": {k: str(v) for k, v in values.items()},
        "max_pairwise_gap_pct": q(gap, "0.000001"),
        "tolerance_pct": str(args.tolerance_pct),
        "status": "PASS" if gap <= d(args.tolerance_pct) else "FLAG",
    })


def verify_valuation(args: argparse.Namespace) -> None:
    price = d(args.price)
    eps, bvps = d(args.eps), d(args.bvps)
    fcf_ps, dividend = d(args.fcf_per_share), d(args.dividend)
    emit({
        "command": "verify-valuation",
        "price": str(price),
        "pe": "N/M" if eps <= 0 else q(price / eps),
        "pb": "N/M" if bvps <= 0 else q(price / bvps),
        "fcf_yield_pct": q(fcf_ps / price * 100),
        "dividend_yield_pct": q(dividend / price * 100),
        "notes": [
            "PE is not meaningful when EPS is non-positive.",
            "A negative FCF yield denotes cash consumption rather than shareholder yield.",
        ],
    })


def metax_valuation(args: argparse.Namespace) -> None:
    price, shares = d(args.price), d(args.shares)
    cash = d(args.cash)
    trading = d(args.trading_assets)
    debt_investments = d(args.debt_investments)
    interest_debt = d(args.interest_debt)
    revenue_ttm, revenue_fy = d(args.revenue_ttm), d(args.revenue_fy)
    net_ttm, equity = d(args.net_ttm), d(args.equity)
    revenue_q1, cost_q1 = d(args.revenue_q1), d(args.cost_q1)
    ocf, capex = d(args.ocf), d(args.capex)
    market_cap = price * shares
    liquid_assets = cash + trading + debt_investments
    net_liquid = liquid_assets - interest_debt
    enterprise_value = market_cap + interest_debt - liquid_assets
    fcf = ocf - capex
    emit({
        "command": "metax-valuation",
        "market_cap": q(market_cap, "0.01"),
        "liquid_assets": q(liquid_assets, "0.01"),
        "net_liquid_assets": q(net_liquid, "0.01"),
        "enterprise_value": q(enterprise_value, "0.01"),
        "ttm_revenue": q(revenue_ttm, "0.01"),
        "ttm_net_profit": q(net_ttm, "0.01"),
        "price_to_ttm_sales": q(market_cap / revenue_ttm),
        "price_to_fy_sales": q(market_cap / revenue_fy),
        "enterprise_value_to_ttm_sales": q(enterprise_value / revenue_ttm),
        "price_to_book": q(market_cap / equity),
        "q1_gross_margin_pct": q((revenue_q1 - cost_q1) / revenue_q1 * 100),
        "free_cash_flow": q(fcf, "0.01"),
        "fcf_per_share": q(fcf / shares),
        "fcf_yield_pct": q(fcf / market_cap * 100),
    })


def scenario_dcf(args: argparse.Namespace) -> None:
    scenarios = load_json(args.scenarios)
    shares = d(args.shares)
    net_cash = d(args.net_cash)
    years = d(args.years)
    discount_rate = d(args.discount_rate)
    discount_factor = (Decimal(1) + discount_rate) ** years
    weighted_price = Decimal(0)
    rows = []
    weight_sum = Decimal(0)
    for name, item in scenarios.items():
        revenue = d(item["revenue"])
        margin = d(item["net_margin"])
        pe = d(item["pe"])
        weight = d(item.get("weight", 0))
        terminal_profit = revenue * margin
        terminal_equity = terminal_profit * pe
        present_equity = terminal_equity / discount_factor + net_cash
        price = present_equity / shares
        rows.append({
            "scenario": name,
            "revenue": q(revenue, "0.01"),
            "net_margin_pct": q(margin * 100),
            "terminal_pe": str(pe),
            "terminal_net_profit": q(terminal_profit, "0.01"),
            "terminal_equity": q(terminal_equity, "0.01"),
            "present_equity_including_current_net_cash": q(present_equity, "0.01"),
            "value_per_share": q(price, "0.01"),
            "weight_pct": q(weight * 100),
        })
        weighted_price += price * weight
        weight_sum += weight
    emit({
        "command": "scenario-dcf",
        "years": str(years),
        "discount_rate_pct": q(discount_rate * 100),
        "discount_factor": q(discount_factor, "0.000001"),
        "net_cash_added_at_present": str(net_cash),
        "scenarios": rows,
        "weight_sum": q(weight_sum),
        "weighted_value_per_share": q(weighted_price, "0.01") if weight_sum == 1 else "N/A",
    })


def reverse_sales(args: argparse.Namespace) -> None:
    market_cap = d(args.market_cap)
    start_revenue = d(args.start_revenue)
    years = d(args.years)
    discount_rate = d(args.discount_rate)
    terminal_multiple = d(args.terminal_multiple)
    future_equity = market_cap * (Decimal(1) + discount_rate) ** years
    required_revenue = future_equity / terminal_multiple
    required_cagr = (required_revenue / start_revenue) ** (Decimal(1) / years) - 1
    emit({
        "command": "reverse-sales",
        "market_cap_today": str(market_cap),
        "years": str(years),
        "discount_rate_pct": q(discount_rate * 100),
        "terminal_sales_multiple": str(terminal_multiple),
        "required_terminal_revenue": q(required_revenue, "0.01"),
        "required_revenue_cagr_pct": q(required_cagr * 100),
    })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    x = sub.add_parser("verify-market-cap")
    x.add_argument("--price", required=True)
    x.add_argument("--shares", required=True)
    x.add_argument("--reported", required=True)
    x.add_argument("--currency", default="CNY")
    x.add_argument("--tolerance-pct", default="1")
    x.set_defaults(func=verify_market_cap)

    x = sub.add_parser("cross-validate")
    x.add_argument("--field", required=True)
    x.add_argument("--values", required=True, help='JSON object, e.g. {"annual":1,"api":1}')
    x.add_argument("--unit", default="")
    x.add_argument("--tolerance-pct", default="1")
    x.set_defaults(func=cross_validate)

    x = sub.add_parser("verify-valuation")
    for name in ("price", "eps", "bvps", "fcf_per_share", "dividend"):
        x.add_argument(f"--{name.replace('_', '-')}", dest=name, required=True)
    x.set_defaults(func=verify_valuation)

    x = sub.add_parser("metax-valuation")
    for name in (
        "price", "shares", "cash", "trading_assets", "debt_investments",
        "interest_debt", "revenue_ttm", "revenue_fy", "net_ttm", "equity",
        "revenue_q1", "cost_q1", "ocf", "capex",
    ):
        x.add_argument(f"--{name.replace('_', '-')}", dest=name, required=True)
    x.set_defaults(func=metax_valuation)

    for command_name in ("scenario-dcf", "three-scenario"):
        x = sub.add_parser(command_name)
        x.add_argument("--scenarios", required=True, help="JSON object")
        x.add_argument("--shares", required=True)
        x.add_argument("--net-cash", required=True)
        x.add_argument("--years", required=True)
        x.add_argument("--discount-rate", required=True, help="Decimal, e.g. 0.12")
        x.set_defaults(func=scenario_dcf)

    x = sub.add_parser("reverse-sales")
    x.add_argument("--market-cap", required=True)
    x.add_argument("--start-revenue", required=True)
    x.add_argument("--years", required=True)
    x.add_argument("--discount-rate", required=True)
    x.add_argument("--terminal-multiple", required=True)
    x.set_defaults(func=reverse_sales)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
