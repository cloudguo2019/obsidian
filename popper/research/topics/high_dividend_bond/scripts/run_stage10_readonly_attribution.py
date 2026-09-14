"""Stage 10 full return attribution from the frozen HD-ANCHOR-001 P00 ledger.

This program never calls the strategy or account engine.  It only aggregates the
already frozen Stage 8 P00 account path and the frozen Stage 9 logical dynamic
batch table.  Dates on or after the historical pseudo-lock start are rejected.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

import pandas as pd


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
FORMAL_DIR = EXPERIMENT / "formal_l2_v1.0_prelock"
FORMAL_MANIFEST = EXPERIMENT / "formal_l2_manifest_v1.0_prelock.json"
FORMAL_RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
STAGE9_MANIFEST = EXPERIMENT / "stage9_readonly_manifest_v1.0_prelock.json"
STAGE9_BATCHES = EXPERIMENT / "stage9_readonly_v1.0_prelock" / "trade_batch_attribution.csv"
PROTOCOL = EXPERIMENT / "preregistration.yaml"
LATEST_PROTOCOL = EXPERIMENT / "preregistration_v1.5_baseline_design_frozen.yaml"
PLAN = EXPERIMENT / "stage10_readonly_attribution_plan_v1.0_pre_results.json"
AUTHORIZATION = EXPERIMENT / "STAGE10_READONLY_ATTRIBUTION_AUTHORIZATION_2026-09-14.md"
ATTEMPT = EXPERIMENT / "stage10_readonly_attribution_attempt_v1.0_prelock.json"
OUTPUT_DIR = EXPERIMENT / "stage10_readonly_v1.0_prelock"
RESULT = EXPERIMENT / "stage10_readonly_result_v1.0_prelock.json"

START = date(2022, 3, 10)
END = date(2025, 9, 10)
STRATEGY = "HD-ANCHOR-001"
BASELINES = ("HD-BASE-000", "HD-BASE-001", "HD-BASE-RM-001")
ACCOUNTS = (STRATEGY, *BASELINES)
TOLERANCE = 0.01

EXPECTED_HASHES = {
    FORMAL_MANIFEST: "6f17406e61a46d034fe6a9f1cc031ee0b614aa927756f0b53e7d49ea54f46196",
    STAGE9_MANIFEST: "1eb1a6e979825ff62e38017bf2b105ac09853b7ad70d61e649da45fb4b7b41f7",
    PROTOCOL: "775e0bb63fa2ffe94cd477a53f0eb68eb5f598b6c92242a6760a3a3d1159be66",
    LATEST_PROTOCOL: "d24c685daa413f57562ec8fda5ca339e2aa5e4fcc7266f27ce7c03eeb0bda82a",
    PLAN: "61733dd752c9a40ef31853ae3cd24b9324a909a8cd090d5313ce89c2fb974a76",
    AUTHORIZATION: "5e5fbb62233466c7229c0856fcaa2c8d320cafafa778281079eb4fa453bed354",
}

SOURCE_NUMERIC = (
    "mark_cny",
    "cash_cny",
    "dividend_receivable_cny",
    "tax_liability_cny",
    "nav_cny",
    "cash_ratio",
    "equity_weight",
    "price_pnl_cny",
    "execution_price_pnl_cny",
    "new_dividend_entitlement_cny",
    "dividend_paid_gross_cny",
    "tax_reserve_change_cny",
    "transaction_fees_cny",
    "expected_nav_change_cny",
    "actual_nav_change_cny",
    "reconciliation_difference_cny",
)
ATTRIBUTION_COMPONENTS = (
    "price_pnl_cny",
    "execution_price_pnl_cny",
    "gross_dividend_entitlement_cny",
    "tax_effect_cny",
    "fee_effect_cny",
    "cash_yield_cny",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def json_load(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def money(value: float) -> float:
    return round(float(value) + 0.0, 2)


def native(value: object) -> object:
    if hasattr(value, "item"):
        return value.item()
    return value


def validate_bound_files(manifest: Mapping[str, object], section: str) -> int:
    checked = 0
    for item in manifest[section]:
        path = REPO_ROOT / item["path"]
        if not path.is_file():
            raise AssertionError(f"bound file missing: {item['path']}")
        if sha256(path) != item["sha256"]:
            raise AssertionError(f"bound file hash changed: {item['path']}")
        checked += 1
    return checked


def validate_inputs() -> dict[str, object]:
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file() or sha256(path) != expected:
            raise AssertionError(f"frozen Stage 10 input changed: {relative_path(path)}")

    plan = json_load(PLAN)
    if plan["status"] != "FROZEN_BEFORE_STAGE10_ATTRIBUTION_RESULTS":
        raise AssertionError("Stage 10 pre-results plan is not frozen")
    if plan["authorized_scope"] != "[2022-03-10, 2025-09-10)":
        raise AssertionError("Stage 10 authorization scope changed")

    formal = json_load(FORMAL_MANIFEST)
    stage9 = json_load(STAGE9_MANIFEST)
    if formal["authorized_scope"] != "[2022-03-10, 2025-09-10)":
        raise AssertionError("formal ledger scope changed")
    if formal["gates"]["historical_pseudo_lock"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("formal manifest historical pseudo-lock status changed")
    if stage9["integrity_validation"]["historical_pseudo_lock"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("Stage 9 historical pseudo-lock status changed")

    formal_checked = validate_bound_files(formal, "result_files")
    stage9_checked = validate_bound_files(stage9, "result_files")
    return {
        "formal_manifest_sha256": EXPECTED_HASHES[FORMAL_MANIFEST],
        "stage9_manifest_sha256": EXPECTED_HASHES[STAGE9_MANIFEST],
        "protocol_sha256": EXPECTED_HASHES[PROTOCOL],
        "latest_protocol_sha256": EXPECTED_HASHES[LATEST_PROTOCOL],
        "plan_sha256": EXPECTED_HASHES[PLAN],
        "authorization_sha256": EXPECTED_HASHES[AUTHORIZATION],
        "formal_result_bindings_checked": formal_checked,
        "stage9_result_bindings_checked": stage9_checked,
    }


def load_p00_daily_accounts() -> pd.DataFrame:
    frame = pd.read_parquet(FORMAL_DIR / "daily_accounts.parquet")
    frame = frame[(frame["profile_id"] == "P00") & frame["account_id"].isin(ACCOUNTS)].copy()
    frame["session_date"] = pd.to_datetime(frame["session_date"]).dt.date
    for column in SOURCE_NUMERIC:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame.sort_values(["account_id", "session_index"]).reset_index(drop=True)

    if set(frame["account_id"]) != set(ACCOUNTS):
        raise AssertionError("P00 account coverage changed")
    dates: list[tuple[date, ...]] = []
    for account_id in ACCOUNTS:
        account = frame[frame["account_id"] == account_id]
        if len(account) != 852 or account["session_date"].nunique() != 852:
            raise AssertionError(f"unexpected P00 row count for {account_id}")
        if account.iloc[0]["session_date"] != START or account.iloc[-1]["session_date"] >= END:
            raise AssertionError(f"P00 date boundary failed for {account_id}")
        dates.append(tuple(account["session_date"]))
    if any(item != dates[0] for item in dates[1:]):
        raise AssertionError("P00 account dates do not align")

    frame["gross_dividend_entitlement_cny"] = frame["new_dividend_entitlement_cny"]
    frame["tax_effect_cny"] = -frame["tax_reserve_change_cny"]
    frame["fee_effect_cny"] = -frame["transaction_fees_cny"]
    frame["cash_yield_cny"] = 0.0
    frame["attributed_nav_change_cny"] = frame[list(ATTRIBUTION_COMPONENTS)].sum(axis=1)
    frame["attribution_difference_cny"] = (
        frame["actual_nav_change_cny"] - frame["attributed_nav_change_cny"]
    )
    return frame


def account_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for account_id in ACCOUNTS:
        account = frame[frame["account_id"] == account_id].sort_values("session_index")
        initial = account.iloc[0]
        terminal = account.iloc[-1]
        components = {column: money(account[column].sum()) for column in ATTRIBUTION_COMPONENTS}
        attributed = money(sum(components.values()))
        nav_gain = money(terminal["nav_cny"] - initial["nav_cny"])
        rows.append({
            "profile_id": "P00",
            "account_id": account_id,
            "start_date": initial["session_date"].isoformat(),
            "end_date": terminal["session_date"].isoformat(),
            "session_rows": len(account),
            "initial_nav_cny": money(initial["nav_cny"]),
            "final_nav_cny": money(terminal["nav_cny"]),
            "nav_gain_cny": nav_gain,
            **components,
            "attributed_nav_gain_cny": attributed,
            "period_identity_difference_cny": money(nav_gain - attributed),
            "sum_actual_nav_change_cny": money(account["actual_nav_change_cny"].sum()),
            "maximum_absolute_daily_reconciliation_cny": money(
                account["reconciliation_difference_cny"].abs().max()
            ),
            "gross_dividend_paid_transfer_cny": money(account["dividend_paid_gross_cny"].sum()),
            "terminal_dividend_receivable_cny": money(terminal["dividend_receivable_cny"]),
            "terminal_tax_liability_cny": money(terminal["tax_liability_cny"]),
            "terminal_cash_cny": money(terminal["cash_cny"]),
            "terminal_shares": int(terminal["shares"]),
            "average_cash_ratio": float(account["cash_ratio"].mean()),
            "average_equity_weight": float(account["equity_weight"].mean()),
        })
    return pd.DataFrame(rows)


def direction_bucket(relative_shares: int, mark_change: float) -> str:
    if relative_shares == 0 or abs(mark_change) < 1e-15:
        return "FLAT"
    if relative_shares > 0 and mark_change > 0:
        return "OVERWEIGHT_UP_GAIN"
    if relative_shares > 0 and mark_change < 0:
        return "OVERWEIGHT_DOWN_LOSS"
    if relative_shares < 0 and mark_change > 0:
        return "UNDERWEIGHT_UP_OPPORTUNITY_LOSS"
    return "UNDERWEIGHT_DOWN_AVOIDED_LOSS"


def relative_daily(frame: pd.DataFrame) -> pd.DataFrame:
    strategy = frame[frame["account_id"] == STRATEGY].sort_values("session_index").copy()
    strategy["opening_shares"] = strategy["shares"].shift(1).fillna(strategy["shares"]).astype(int)
    strategy["mark_change_cny"] = strategy["mark_cny"].diff().fillna(0.0)
    rows: list[pd.DataFrame] = []
    for baseline_id in BASELINES:
        baseline = frame[frame["account_id"] == baseline_id].sort_values("session_index").copy()
        baseline["opening_shares"] = baseline["shares"].shift(1).fillna(baseline["shares"]).astype(int)
        merged = strategy.merge(
            baseline,
            on=["profile_id", "session_date", "session_index"],
            suffixes=("__strategy", "__baseline"),
            validate="one_to_one",
        )
        result = pd.DataFrame({
            "profile_id": "P00",
            "baseline_account_id": baseline_id,
            "session_date": merged["session_date"],
            "session_index": merged["session_index"],
            "mark_cny": merged["mark_cny__strategy"],
            "mark_change_cny": merged["mark_change_cny"],
            "strategy_opening_shares": merged["opening_shares__strategy"].astype(int),
            "baseline_opening_shares": merged["opening_shares__baseline"].astype(int),
            "relative_opening_shares": (
                merged["opening_shares__strategy"] - merged["opening_shares__baseline"]
            ).astype(int),
            "strategy_closing_shares": merged["shares__strategy"].astype(int),
            "baseline_closing_shares": merged["shares__baseline"].astype(int),
            "relative_closing_shares": (
                merged["shares__strategy"] - merged["shares__baseline"]
            ).astype(int),
        })
        for component in ATTRIBUTION_COMPONENTS:
            result[f"relative_{component}"] = (
                merged[f"{component}__strategy"] - merged[f"{component}__baseline"]
            )
        result["relative_attributed_nav_change_cny"] = result[
            [f"relative_{item}" for item in ATTRIBUTION_COMPONENTS]
        ].sum(axis=1)
        result["relative_actual_nav_change_cny"] = (
            merged["actual_nav_change_cny__strategy"] - merged["actual_nav_change_cny__baseline"]
        )
        result["relative_identity_difference_cny"] = (
            result["relative_actual_nav_change_cny"]
            - result["relative_attributed_nav_change_cny"]
        )
        result["price_direction_bucket"] = [
            direction_bucket(int(shares), float(change))
            for shares, change in zip(result["relative_opening_shares"], result["mark_change_cny"])
        ]
        expected_price = result["relative_opening_shares"] * result["mark_change_cny"]
        if (expected_price - result["relative_price_pnl_cny"]).abs().max() > TOLERANCE:
            raise AssertionError(f"relative price exposure formula failed for {baseline_id}")
        rows.append(result)
    return pd.concat(rows, ignore_index=True)


def bucket_amount(group: pd.DataFrame, bucket: str) -> float:
    return money(group.loc[group["price_direction_bucket"] == bucket, "relative_price_pnl_cny"].sum())


def relative_summary(daily: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    account_map = accounts.set_index("account_id")
    rows: list[dict[str, object]] = []
    for baseline_id in BASELINES:
        group = daily[daily["baseline_account_id"] == baseline_id]
        strategy_final = float(account_map.loc[STRATEGY, "final_nav_cny"])
        baseline_final = float(account_map.loc[baseline_id, "final_nav_cny"])
        terminal_difference = money(strategy_final - baseline_final)
        components = {
            component: money(group[f"relative_{component}"].sum())
            for component in ATTRIBUTION_COMPONENTS
        }
        attributed = money(sum(components.values()))
        underweight_up = bucket_amount(group, "UNDERWEIGHT_UP_OPPORTUNITY_LOSS")
        overweight_down = bucket_amount(group, "OVERWEIGHT_DOWN_LOSS")
        rows.append({
            "profile_id": "P00",
            "strategy_account_id": STRATEGY,
            "baseline_account_id": baseline_id,
            "terminal_nav_difference_cny": terminal_difference,
            **{f"relative_{key}": value for key, value in components.items()},
            "relative_attributed_nav_change_cny": attributed,
            "relative_period_identity_difference_cny": money(terminal_difference - attributed),
            "overweight_up_gain_cny": bucket_amount(group, "OVERWEIGHT_UP_GAIN"),
            "overweight_down_loss_cny": money(-overweight_down),
            "underweight_up_opportunity_loss_cny": money(-underweight_up),
            "underweight_down_avoided_loss_cny": bucket_amount(
                group, "UNDERWEIGHT_DOWN_AVOIDED_LOSS"
            ),
            "flat_price_component_cny": bucket_amount(group, "FLAT"),
            "average_relative_opening_shares": float(group["relative_opening_shares"].mean()),
            "minimum_relative_opening_shares": int(group["relative_opening_shares"].min()),
            "maximum_relative_opening_shares": int(group["relative_opening_shares"].max()),
        })
    return pd.DataFrame(rows)


def annual_attribution(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    frame["calendar_year"] = frame["session_date"].map(lambda value: value.year)
    rows: list[dict[str, object]] = []
    for (baseline_id, year), group in frame.groupby(["baseline_account_id", "calendar_year"]):
        components = {
            component: money(group[f"relative_{component}"].sum())
            for component in ATTRIBUTION_COMPONENTS
        }
        attributed = money(sum(components.values()))
        actual = money(group["relative_actual_nav_change_cny"].sum())
        rows.append({
            "profile_id": "P00",
            "baseline_account_id": baseline_id,
            "calendar_year": int(year),
            "session_rows": len(group),
            **{f"relative_{key}": value for key, value in components.items()},
            "relative_attributed_nav_change_cny": attributed,
            "relative_actual_nav_change_cny": actual,
            "relative_identity_difference_cny": money(actual - attributed),
        })
    return pd.DataFrame(rows).sort_values(["baseline_account_id", "calendar_year"])


def inventory_segments(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for baseline_id in BASELINES:
        frame = daily[daily["baseline_account_id"] == baseline_id].sort_values("session_index").copy()
        frame["segment_number"] = (
            frame["strategy_opening_shares"].ne(frame["strategy_opening_shares"].shift()).cumsum()
        )
        for segment_number, group in frame.groupby("segment_number", sort=True):
            components = {
                component: money(group[f"relative_{component}"].sum())
                for component in ATTRIBUTION_COMPONENTS
            }
            attributed = money(sum(components.values()))
            actual = money(group["relative_actual_nav_change_cny"].sum())
            rows.append({
                "profile_id": "P00",
                "baseline_account_id": baseline_id,
                "segment_id": f"{baseline_id}-SEG-{int(segment_number):02d}",
                "start_date": group.iloc[0]["session_date"].isoformat(),
                "end_date": group.iloc[-1]["session_date"].isoformat(),
                "session_rows": len(group),
                "strategy_opening_shares": int(group.iloc[0]["strategy_opening_shares"]),
                "baseline_opening_shares": int(group.iloc[0]["baseline_opening_shares"]),
                "relative_opening_shares": int(group.iloc[0]["relative_opening_shares"]),
                **{f"relative_{key}": value for key, value in components.items()},
                "relative_attributed_nav_change_cny": attributed,
                "relative_actual_nav_change_cny": actual,
                "relative_identity_difference_cny": money(actual - attributed),
                "overweight_up_gain_cny": bucket_amount(group, "OVERWEIGHT_UP_GAIN"),
                "overweight_down_loss_cny": money(-bucket_amount(group, "OVERWEIGHT_DOWN_LOSS")),
                "underweight_up_opportunity_loss_cny": money(
                    -bucket_amount(group, "UNDERWEIGHT_UP_OPPORTUNITY_LOSS")
                ),
                "underweight_down_avoided_loss_cny": bucket_amount(
                    group, "UNDERWEIGHT_DOWN_AVOIDED_LOSS"
                ),
            })
    return pd.DataFrame(rows)


def dynamic_batches() -> tuple[pd.DataFrame, dict[str, object]]:
    source = pd.read_csv(STAGE9_BATCHES)
    if len(source) != 5:
        raise AssertionError("frozen Stage 9 dynamic batch count changed")
    numeric = (
        "shares", "buy_price_cny", "buy_fees_cny", "sell_price_cny", "sell_fees_cny",
        "deferred_tax_paid_cny", "exit_or_mark_price_cny", "gross_dividend_entitlements_cny",
        "net_contribution_cny",
    )
    for column in numeric:
        source[column] = pd.to_numeric(source[column], errors="coerce").fillna(0.0)
    source["price_spread_cny"] = (
        (source["exit_or_mark_price_cny"] - source["buy_price_cny"]) * source["shares"]
    )
    source["transaction_fees_cny"] = source["buy_fees_cny"] + source["sell_fees_cny"]
    source["tax_effect_cny"] = -source["deferred_tax_paid_cny"]
    source["calculated_net_contribution_cny"] = (
        source["price_spread_cny"]
        + source["gross_dividend_entitlements_cny"]
        - source["transaction_fees_cny"]
        + source["tax_effect_cny"]
    )
    source["batch_identity_difference_cny"] = (
        source["net_contribution_cny"] - source["calculated_net_contribution_cny"]
    )
    if source["batch_identity_difference_cny"].abs().max() > TOLERANCE:
        raise AssertionError("dynamic batch component identity failed")
    source["realized_price_spread_cny"] = source["price_spread_cny"].where(
        source["status"] == "CLOSED_LOGICAL_DYNAMIC_BATCH", 0.0
    )
    source["terminal_unrealized_price_spread_cny"] = source["price_spread_cny"].where(
        source["status"] == "OPEN_MARKED_AT_TERMINAL", 0.0
    )
    for column in (
        "price_spread_cny", "transaction_fees_cny", "tax_effect_cny",
        "calculated_net_contribution_cny", "batch_identity_difference_cny",
        "realized_price_spread_cny", "terminal_unrealized_price_spread_cny",
    ):
        source[column] = source[column].map(money)

    contributions = source["net_contribution_cny"].astype(float)
    absolute_total = float(contributions.abs().sum())
    positive = source[source["net_contribution_cny"] > 0].sort_values(
        "net_contribution_cny", ascending=False
    )
    largest = positive.iloc[0]
    summary = {
        "dynamic_buy_batches": len(source),
        "closed_logical_batches": int((source["status"] == "CLOSED_LOGICAL_DYNAMIC_BATCH").sum()),
        "terminal_open_logical_batches": int((source["status"] == "OPEN_MARKED_AT_TERMINAL").sum()),
        "total_net_contribution_cny": money(contributions.sum()),
        "closed_net_contribution_cny": money(
            source.loc[source["status"] == "CLOSED_LOGICAL_DYNAMIC_BATCH", "net_contribution_cny"].sum()
        ),
        "terminal_open_net_contribution_cny": money(
            source.loc[source["status"] == "OPEN_MARKED_AT_TERMINAL", "net_contribution_cny"].sum()
        ),
        "realized_price_spread_cny": money(source["realized_price_spread_cny"].sum()),
        "terminal_unrealized_price_spread_cny": money(
            source["terminal_unrealized_price_spread_cny"].sum()
        ),
        "gross_dividend_entitlements_cny": money(source["gross_dividend_entitlements_cny"].sum()),
        "transaction_fees_cny": money(source["transaction_fees_cny"].sum()),
        "deferred_tax_paid_cny": money(source["deferred_tax_paid_cny"].sum()),
        "largest_positive_batch_id": str(largest["batch_id"]),
        "largest_positive_batch_contribution_cny": money(largest["net_contribution_cny"]),
        "negative_batch_contribution_cny": money(contributions[contributions < 0].sum()),
        "absolute_batch_contribution_cny": money(absolute_total),
        "largest_absolute_contribution_fraction": (
            None if absolute_total == 0 else float(contributions.abs().max() / absolute_total)
        ),
        "top3_absolute_contribution_fraction": (
            None if absolute_total == 0 else float(contributions.abs().nlargest(3).sum() / absolute_total)
        ),
    }
    return source, summary


def fee_breakdown() -> tuple[pd.DataFrame, dict[str, object]]:
    outcomes = pd.read_parquet(FORMAL_DIR / "auction_outcomes_daily_close_lagged.parquet")
    outcomes = outcomes[
        (outcomes["profile_id"] == "P00")
        & (outcomes["account_id"] == STRATEGY)
        & (outcomes["status"].isin(["FILLED", "PARTIAL"]))
    ].copy()
    if len(outcomes) != 9:
        raise AssertionError("P00 filled order count changed")
    totals: dict[str, float] = {}
    for raw in outcomes["fee_components_cny"]:
        components = json.loads(raw)
        for name, value in components.items():
            totals[name] = totals.get(name, 0.0) + float(value)
    total_fees = money(pd.to_numeric(outcomes["total_fees_cny"], errors="raise").sum())
    component_sum = money(sum(totals.values()))
    if abs(total_fees - component_sum) > TOLERANCE:
        raise AssertionError("fee component sum does not match total transaction fees")
    deferred_tax = money(pd.to_numeric(outcomes["deferred_tax_paid_cny"], errors="raise").sum())
    rows = [
        {
            "item": name,
            "amount_cny": money(amount),
            "classification": "TRANSACTION_FEE_SUBCOMPONENT",
            "included_in_nav_fee_effect": True,
            "note": "Subcomponent of TOTAL_TRANSACTION_FEES; do not add both views.",
        }
        for name, amount in sorted(totals.items())
    ]
    rows.extend([
        {
            "item": "TOTAL_TRANSACTION_FEES",
            "amount_cny": total_fees,
            "classification": "NAV_ATTRIBUTION_TOTAL",
            "included_in_nav_fee_effect": True,
            "note": "Used once as the negative fee contribution in the NAV identity.",
        },
        {
            "item": "DEFERRED_DIVIDEND_TAX_PAID",
            "amount_cny": deferred_tax,
            "classification": "LIABILITY_SETTLEMENT_NOT_NEW_EXPENSE",
            "included_in_nav_fee_effect": False,
            "note": "Cash and an already recognized tax liability decline together; do not expense twice.",
        },
    ])
    return pd.DataFrame(rows), {
        "filled_parent_orders": len(outcomes),
        "fee_subcomponents_cny": {key: money(value) for key, value in sorted(totals.items())},
        "total_transaction_fees_cny": total_fees,
        "deferred_dividend_tax_paid_cny": deferred_tax,
    }


def annual_concentration(annual: pd.DataFrame) -> dict[str, object]:
    frame = annual[annual["baseline_account_id"] == "HD-BASE-RM-001"].copy()
    values = frame.set_index("calendar_year")["relative_actual_nav_change_cny"].astype(float)
    absolute_total = float(values.abs().sum())
    maximum_positive_year = int(values.idxmax())
    maximum_absolute_year = int(values.abs().idxmax())
    return {
        "calendar_years": len(values),
        "relative_nav_change_by_year_cny": {str(int(key)): money(value) for key, value in values.items()},
        "maximum_positive_year": maximum_positive_year,
        "maximum_positive_year_contribution_cny": money(values.loc[maximum_positive_year]),
        "maximum_absolute_year": maximum_absolute_year,
        "maximum_absolute_year_contribution_cny": money(values.loc[maximum_absolute_year]),
        "absolute_annual_contribution_cny": money(absolute_total),
        "largest_absolute_year_fraction": (
            None if absolute_total == 0 else float(values.abs().max() / absolute_total)
        ),
        "top3_absolute_year_fraction": (
            None if absolute_total == 0 else float(values.abs().nlargest(3).sum() / absolute_total)
        ),
    }


def execute() -> dict[str, object]:
    if OUTPUT_DIR.exists() or RESULT.exists() or ATTEMPT.exists():
        raise FileExistsError("Stage 10 attempt/output already exists; immutable artifacts will not be overwritten")
    input_checks = validate_inputs()
    formal_result = json_load(FORMAL_RESULT)
    if formal_result["locked_period_status"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("historical pseudo-lock is no longer closed")

    write_json(ATTEMPT, {
        "statement_type": "已观察事实",
        "experiment_id": "HD-ANCHOR-001",
        "attempt_version": "HD-STAGE10-READONLY-ATTRIBUTION-ATTEMPT-1.0-PRELOCK",
        "consumed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "ONE_AUTHORIZED_READONLY_ATTRIBUTION_ATTEMPT_CONSUMED",
        "authorized_scope": "[2022-03-10, 2025-09-10)",
        "plan_sha256": EXPECTED_HASHES[PLAN],
        "strategy_run_count_increment": 0,
        "performance_path_calculation_count_increment": 0,
        "historical_pseudo_lock_open_count_increment": 0,
        "dry_run": True,
    })

    daily_source = load_p00_daily_accounts()
    accounts = account_summary(daily_source)
    daily = relative_daily(daily_source)
    relative = relative_summary(daily, accounts)
    annual = annual_attribution(daily)
    segments = inventory_segments(daily)
    batches, batch_summary = dynamic_batches()
    fees, fee_summary = fee_breakdown()

    maximum_daily_reconciliation = float(
        daily_source["reconciliation_difference_cny"].abs().max()
    )
    maximum_account_period_difference = float(accounts["period_identity_difference_cny"].abs().max())
    maximum_relative_difference = float(relative["relative_period_identity_difference_cny"].abs().max())
    maximum_annual_difference = float(annual["relative_identity_difference_cny"].abs().max())
    maximum_segment_difference = float(segments["relative_identity_difference_cny"].abs().max())
    overlay = relative.set_index("baseline_account_id").loc["HD-BASE-000"]
    overlay_batch_difference = money(
        float(overlay["terminal_nav_difference_cny"]) - batch_summary["total_net_contribution_cny"]
    )

    checks = {
        "maximum_daily_account_reconciliation_cny": money(maximum_daily_reconciliation),
        "maximum_period_account_identity_difference_cny": money(maximum_account_period_difference),
        "maximum_relative_identity_difference_cny": money(maximum_relative_difference),
        "maximum_annual_relative_identity_difference_cny": money(maximum_annual_difference),
        "maximum_segment_relative_identity_difference_cny": money(maximum_segment_difference),
        "dynamic_overlay_batch_difference_cny": overlay_batch_difference,
    }
    if maximum_daily_reconciliation > TOLERANCE:
        raise AssertionError("daily account reconciliation exceeds CNY 0.01")
    if maximum_account_period_difference > TOLERANCE:
        raise AssertionError("period account identity exceeds CNY 0.01")
    if maximum_relative_difference > TOLERANCE or maximum_annual_difference > TOLERANCE:
        raise AssertionError("relative component identity exceeds CNY 0.01")
    if maximum_segment_difference > TOLERANCE:
        raise AssertionError("inventory segment identity exceeds CNY 0.01")
    if abs(overlay_batch_difference) > TOLERANCE:
        raise AssertionError("dynamic batches do not reconcile to the 1000-share core overlay")

    annual_summary = annual_concentration(annual)
    relative_map = {
        str(row["baseline_account_id"]): {
            str(key): native(value)
            for key, value in row.items()
            if key != "baseline_account_id"
        }
        for row in relative.to_dict(orient="records")
    }
    details = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE10-READONLY-DETAILS-1.0-PRELOCK",
        "authorized_scope": "[2022-03-10, 2025-09-10)",
        "accounting_identity": checks,
        "relative_attribution": relative_map,
        "dynamic_grid_batches": batch_summary,
        "fee_breakdown": fee_summary,
        "annual_concentration_vs_risk_matched": annual_summary,
        "interpretation_boundaries": [
            "Dividend payment is a receivable-to-cash transfer and is not added again after ex-date entitlement recognition.",
            "Cash yield is exactly zero under P00 and every P00 static comparator; cash opportunity cost is expressed through relative stock price and dividend exposure.",
            "Dynamic batch, benchmark opportunity-cost, and total component views overlap and must not be added together.",
            "All results remain retrospective L2 and do not open or weaken the historical pseudo-lock.",
        ],
    }

    temp_parent = Path(tempfile.mkdtemp(prefix="stage10_tmp_", dir=EXPERIMENT))
    accounts.to_csv(temp_parent / "account_component_summary.csv", index=False, encoding="utf-8")
    relative.to_csv(temp_parent / "relative_component_summary.csv", index=False, encoding="utf-8")
    annual.to_csv(temp_parent / "annual_relative_attribution.csv", index=False, encoding="utf-8")
    segments.to_csv(temp_parent / "inventory_opportunity_segments.csv", index=False, encoding="utf-8")
    batches.to_csv(temp_parent / "dynamic_batch_attribution.csv", index=False, encoding="utf-8")
    fees.to_csv(temp_parent / "fee_breakdown.csv", index=False, encoding="utf-8")
    daily_out = daily.copy()
    daily_out["session_date"] = daily_out["session_date"].map(lambda value: value.isoformat())
    daily_out.to_parquet(temp_parent / "daily_attribution.parquet", index=False)
    write_json(temp_parent / "stage10_details.json", details)
    os.replace(temp_parent, OUTPUT_DIR)

    primary = relative_map["HD-BASE-RM-001"]
    maximum_inventory = relative_map["HD-BASE-001"]
    result = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE10-READONLY-ATTRIBUTION-RESULT-1.0-PRELOCK",
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "status": "PASS_STAGE10_FULL_RETURN_ATTRIBUTION_FROM_FROZEN_LEDGER",
        "authorized_scope": "[2022-03-10, 2025-09-10)",
        "strategy_run_count_increment": 0,
        "performance_path_calculation_count_increment": 0,
        "stage10_readonly_attribution_run_count": 1,
        "historical_pseudo_lock_open_count_increment": 0,
        "input_checks": input_checks,
        "output_rows": {
            "daily_attribution": len(daily),
            "account_component_summary": len(accounts),
            "relative_component_summary": len(relative),
            "annual_relative_attribution": len(annual),
            "inventory_opportunity_segments": len(segments),
            "dynamic_batch_attribution": len(batches),
            "fee_breakdown": len(fees),
        },
        "accounting_identity": checks,
        "primary_attribution_vs_risk_matched": primary,
        "dynamic_overlay_vs_1000_share_core": {
            **relative_map["HD-BASE-000"],
            "frozen_dynamic_batch_total_net_contribution_cny": batch_summary["total_net_contribution_cny"],
            "overlay_batch_difference_cny": overlay_batch_difference,
        },
        "opportunity_cost_vs_1500_share_static": maximum_inventory,
        "dynamic_grid_batches": batch_summary,
        "fee_breakdown": fee_summary,
        "annual_concentration_vs_risk_matched": annual_summary,
        "research_decision": "修改",
        "decision_effect": "ATTRIBUTION_ONLY;_STAGE8_RISK_RECOVERY_AND_CONFIRMATORY_FAILURES_REMAIN",
        "evidence_ceiling": "L2_RETROSPECTIVE",
        "historical_pseudo_lock_status": "NOT_OPENED_NOT_READ",
        "next_gate": "STAGE11_FORMAL_REPORT_USING_FROZEN_STAGE8_STAGE9_AND_STAGE10_ARTIFACTS",
    }
    write_json(RESULT, result)
    return result


if __name__ == "__main__":
    print(json.dumps(execute(), ensure_ascii=False, indent=2))
