"""Read-only Stage 9 robustness and falsification analysis for HD-ANCHOR-001.

This program never runs the strategy state machine. It reads only the frozen
Stage 8 pre-lock ledgers/results and audited inputs needed to construct the
pre-registered decision-time market-state labels. The historical pseudo-lock
beginning 2025-09-10 is outside every result and price-performance read.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import sys
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TOPIC_ROOT))

from engine.stage8_engine import load_corporate_actions  # noqa: E402


EXPERIMENT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
DATASETS = TOPIC_ROOT / "datasets"
FORMAL_DIR = EXPERIMENT / "formal_l2_v1.0_prelock"
FORMAL_MANIFEST = EXPERIMENT / "formal_l2_manifest_v1.0_prelock.json"
FORMAL_RESULT = EXPERIMENT / "formal_l2_result_v1.0_prelock.json"
PROTOCOL = EXPERIMENT / "preregistration.yaml"
PLAN = EXPERIMENT / "stage9_readonly_analysis_plan_v1.0_pre_results.json"
AUTHORIZATION = EXPERIMENT / "STAGE9_READONLY_AUTHORIZATION_2026-09-13.md"
PRICE = DATASETS / "cleaned" / "cleaned_price.csv"
PIT = DATASETS / "cleaned" / "point_in_time_dividend_estimates.csv"
ACTIONS = DATASETS / "cleaned" / "corporate_actions.csv"

OUTPUT_DIR = EXPERIMENT / "stage9_readonly_v1.0_prelock"
RESULT = EXPERIMENT / "stage9_readonly_result_v1.0_prelock.json"

START = date(2022, 3, 10)
END = date(2025, 9, 10)
HISTORY_START = date(2020, 1, 1)
ACCOUNT_IDS = (
    "HD-ANCHOR-001",
    "HD-BASE-000",
    "HD-BASE-001",
    "HD-BASE-RM-001",
)
REQUIRED_ROBUSTNESS = ("P01", "P03", "P05", "P06", "P10")
LOCAL_NEIGHBORS = ("P15", "P16", "P17", "P18")

EXPECTED_FORMAL_MANIFEST_SHA256 = (
    "6f17406e61a46d034fe6a9f1cc031ee0b614aa927756f0b53e7d49ea54f46196"
)
EXPECTED_PROTOCOL_SHA256 = (
    "775e0bb63fa2ffe94cd477a53f0eb68eb5f598b6c92242a6760a3a3d1159be66"
)
EXPECTED_PLAN_SHA256 = (
    "436889b454fda1e2e2591dfb9d1826241d7dd413b3042f6a342803d6cbe545b2"
)
EXPECTED_AUTHORIZATION_SHA256 = (
    "63c213640be6fa989f05d0db9dd32474bb5a64ff52424903bb019bb1f63fbf22"
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


def scalar(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def clean_record(record: Mapping[str, object]) -> dict[str, object]:
    return {str(key): scalar(value) for key, value in record.items()}


def parse_dt(value: object) -> datetime | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return datetime.fromisoformat(str(value))


def validate_frozen_inputs() -> dict[str, object]:
    if sha256(FORMAL_MANIFEST) != EXPECTED_FORMAL_MANIFEST_SHA256:
        raise AssertionError("formal Stage 8 manifest hash changed")
    if sha256(PROTOCOL) != EXPECTED_PROTOCOL_SHA256:
        raise AssertionError("frozen base protocol hash changed")
    if sha256(PLAN) != EXPECTED_PLAN_SHA256:
        raise AssertionError("Stage 9 pre-results plan hash changed")
    if sha256(AUTHORIZATION) != EXPECTED_AUTHORIZATION_SHA256:
        raise AssertionError("Stage 9 authorization hash changed")

    manifest = json_load(FORMAL_MANIFEST)
    checked = 0
    for item in manifest["result_files"]:
        path = REPO_ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise AssertionError(f"frozen Stage 8 result binding failed: {item['path']}")
        checked += 1
    if manifest["authorized_scope"] != "[2022-03-10, 2025-09-10)":
        raise AssertionError("formal manifest scope changed")
    if manifest["gates"]["historical_pseudo_lock"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("historical pseudo-lock status changed")

    protocol = json_load(PROTOCOL)
    diagnostics = protocol["diagnostics_and_falsification"]
    if "过去126交易日收益>=10%标上涨、<=-10%标下跌" not in diagnostics["market_states"]:
        raise AssertionError("pre-registered market-state thresholds changed")
    if "只用t-1之前资料分类" not in diagnostics["regime_inputs"]:
        raise AssertionError("decision-time regime information rule changed")
    return {
        "formal_manifest_sha256": EXPECTED_FORMAL_MANIFEST_SHA256,
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "plan_sha256": EXPECTED_PLAN_SHA256,
        "authorization_sha256": EXPECTED_AUTHORIZATION_SHA256,
        "formal_result_bindings_checked": checked,
    }


def load_total_return_history() -> pd.DataFrame:
    action_dps: dict[date, Decimal] = {}
    for action in load_corporate_actions(ACTIONS):
        if action.ex_date >= END:
            continue
        action_dps[action.ex_date] = action_dps.get(action.ex_date, Decimal("0")) + (
            action.cash_dividend_per_share
        )

    rows: list[dict[str, object]] = []
    with PRICE.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            session_date = date.fromisoformat(row["session_date"])
            if session_date >= END:
                break
            if session_date < HISTORY_START or row["trade_status"] != "TRADING":
                continue
            if not row["close"]:
                raise AssertionError(f"tradable price has no close: {session_date}")
            rows.append({
                "session_date": session_date,
                "close": float(row["close"]),
                "cash_entitlement_per_share": float(action_dps.get(session_date, Decimal("0"))),
            })
    frame = pd.DataFrame(rows).sort_values("session_date").reset_index(drop=True)
    if frame.empty or frame.iloc[-1]["session_date"] >= END:
        raise AssertionError("price boundary failed")
    gross = [1.0]
    one_day_return = [math.nan]
    for index in range(1, len(frame)):
        previous_close = float(frame.iloc[index - 1]["close"])
        current_close = float(frame.iloc[index]["close"])
        dividend = float(frame.iloc[index]["cash_entitlement_per_share"])
        value = (current_close + dividend) / previous_close
        if value <= 0:
            raise AssertionError("non-positive underlying total-return gross factor")
        gross.append(gross[-1] * value)
        one_day_return.append(value - 1.0)
    frame["total_return_index"] = gross
    frame["underlying_total_return"] = one_day_return

    trends: list[str] = []
    high_vols: list[object] = []
    trailing_returns: list[object] = []
    trailing_vols: list[object] = []
    for index in range(len(frame)):
        if index < 127:
            trailing_returns.append(math.nan)
            trends.append("UNCLASSIFIED")
        else:
            trailing = frame.iloc[index - 1]["total_return_index"] / frame.iloc[index - 127][
                "total_return_index"
            ] - 1.0
            trailing_returns.append(trailing)
            trends.append("UP" if trailing >= 0.10 else "DOWN" if trailing <= -0.10 else "SIDEWAYS")
        if index < 22:
            trailing_vols.append(math.nan)
            high_vols.append(None)
        else:
            values = frame.iloc[index - 21:index]["underlying_total_return"].astype(float).tolist()
            if len(values) != 21 or any(math.isnan(value) for value in values):
                raise AssertionError("21-session volatility window is incomplete")
            volatility = statistics.stdev(values) * math.sqrt(252)
            trailing_vols.append(volatility)
            high_vols.append(volatility >= 0.30)
    frame["trailing_126_total_return_t_minus_1"] = trailing_returns
    frame["trailing_21_annualized_volatility_t_minus_1"] = trailing_vols
    frame["trend_state"] = trends
    frame["high_vol"] = high_vols
    frame["vol_state"] = [
        "UNCLASSIFIED" if value is None else "HIGH_VOL" if value else "NORMAL_VOL"
        for value in high_vols
    ]
    frame["combined_state"] = frame["trend_state"] + "|" + frame["vol_state"]
    return frame


def profile_robustness() -> tuple[pd.DataFrame, dict[str, object]]:
    profiles = json_load(FORMAL_DIR / "profile_results.json")
    bootstrap = json_load(FORMAL_DIR / "bootstrap_intervals.json")
    ci_lookup = {
        (item["profile_id"], item["comparator_id"], int(item["expected_block_length_sessions"])): item
        for item in bootstrap
    }
    rows: list[dict[str, object]] = []
    for index in range(24):
        profile_id = f"P{index:02d}"
        profile = profiles[profile_id]
        row: dict[str, object] = {
            "profile_id": profile_id,
            "status": profile["status"],
            "description": profile.get("description"),
            "required_robustness_gate": profile_id in REQUIRED_ROBUSTNESS,
            "local_parameter_neighbor": profile_id in LOCAL_NEIGHBORS,
            "not_run_reason": profile.get("reason"),
        }
        if profile["status"] == "COMPLETED":
            comparison = profile["comparisons"]["HD-BASE-RM-001"]
            metrics = profile["paths"]["HD-ANCHOR-001"]
            ci = ci_lookup[(profile_id, "HD-BASE-RM-001", 60)]
            windows = [
                item for item in profile["window_effects"]["HD-BASE-RM-001"]
                if item["status"] == "PASS"
            ]
            row.update({
                "delta_cagr": float(comparison["delta_cagr"]),
                "delta_total_return": float(comparison["delta_total_return"]),
                "ci_60_lower": float(ci["ci_lower"]),
                "ci_60_upper": float(ci["ci_upper"]),
                "ci_60_excludes_zero_positive": float(ci["ci_lower"]) > 0,
                "max_drawdown": float(metrics["max_drawdown"]),
                "max_drawdown_difference": float(comparison["max_drawdown_difference"]),
                "mean_equity_weight_absolute_difference": float(
                    comparison["absolute_mean_equity_weight_difference"]
                ),
                "filled_parent_orders": int(metrics["filled_parent_orders"]),
                "transition_clusters": int(metrics["transition_clusters_20_session_gap"]),
                "positive_windows": sum(float(item["increment"]) > 0 for item in windows),
                "eligible_windows": len(windows),
            })
        rows.append(row)
    frame = pd.DataFrame(rows)
    completed = frame[frame["status"] == "COMPLETED"]
    required_pass = bool(
        (frame.set_index("profile_id").loc[list(REQUIRED_ROBUSTNESS), "delta_cagr"] >= 0).all()
    )
    local_nonnegative = int(
        (frame.set_index("profile_id").loc[list(LOCAL_NEIGHBORS), "delta_cagr"] >= 0).sum()
    )
    summary = {
        "registered_profiles": 24,
        "completed_profiles": int((frame["status"] == "COMPLETED").sum()),
        "not_run_profiles": int((frame["status"] == "NOT_RUN").sum()),
        "completed_point_estimates_nonnegative": int((completed["delta_cagr"] >= 0).sum()),
        "completed_ci_60_excludes_zero_positive": int(
            completed["ci_60_excludes_zero_positive"].sum()
        ),
        "required_profiles": list(REQUIRED_ROBUSTNESS),
        "required_profiles_nonnegative_gate": "PASS" if required_pass else "FAIL",
        "local_neighbors": list(LOCAL_NEIGHBORS),
        "local_neighbors_nonnegative": local_nonnegative,
        "local_neighbor_gate": "PASS" if local_nonnegative >= 3 else "FAIL",
        "minimum_delta_cagr_profile": str(completed.loc[completed["delta_cagr"].idxmin(), "profile_id"]),
        "minimum_delta_cagr": float(completed["delta_cagr"].min()),
        "maximum_delta_cagr_profile": str(completed.loc[completed["delta_cagr"].idxmax(), "profile_id"]),
        "maximum_delta_cagr": float(completed["delta_cagr"].max()),
        "P21_status": str(frame.set_index("profile_id").loc["P21", "status"]),
        "P22_P23_activation": "NOT_ACTIVATED_FEWER_THAN_10_OTHERWISE_FILLABLE_PARENT_ORDERS",
    }
    return frame, summary


def load_p00_ledgers() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = pd.read_parquet(FORMAL_DIR / "daily_accounts.parquet")
    daily = daily[(daily["profile_id"] == "P00") & daily["account_id"].isin(ACCOUNT_IDS)].copy()
    daily["session_date"] = pd.to_datetime(daily["session_date"]).dt.date
    if set(daily["account_id"].unique()) != set(ACCOUNT_IDS):
        raise AssertionError("P00 account set is incomplete")
    if daily["session_date"].max() >= END:
        raise AssertionError("daily ledger crossed the authorized boundary")
    for column in (
        "mark_cny", "nav_cny", "daily_return", "drawdown", "equity_weight", "cash_ratio",
        "new_dividend_entitlement_cny", "transaction_fees_cny",
    ):
        daily[column] = pd.to_numeric(daily[column], errors="coerce")

    signals = pd.read_parquet(FORMAL_DIR / "daily_close_signal_and_lagged_orders.parquet")
    signals = signals[signals["profile_id"] == "P00"].copy()
    signals["session_date"] = pd.to_datetime(signals["session_date"]).dt.date
    signals["execute_session_date"] = pd.to_datetime(
        signals["execute_session_date"], errors="coerce"
    ).dt.date
    if signals["session_date"].max() >= END:
        raise AssertionError("signal ledger crossed the authorized boundary")

    outcomes = pd.read_parquet(FORMAL_DIR / "auction_outcomes_daily_close_lagged.parquet")
    outcomes = outcomes[outcomes["profile_id"] == "P00"].copy()
    outcomes["session_date"] = pd.to_datetime(outcomes["session_date"]).dt.date
    if outcomes["session_date"].dropna().max() >= END:
        raise AssertionError("outcome ledger crossed the authorized boundary")
    for column in (
        "fill_price_cny", "reference_price_cny", "total_fees_cny", "deferred_tax_paid_cny",
    ):
        outcomes[column] = pd.to_numeric(outcomes[column], errors="coerce")
    return daily, signals, outcomes


def episode_ids(values: Sequence[str]) -> list[int]:
    result: list[int] = []
    current = 0
    previous: str | None = None
    for value in values:
        if value != previous:
            current += 1
        result.append(current)
        previous = value
    return result


def episode_path_stats(returns: Sequence[float]) -> dict[str, object]:
    wealth = 1.0
    high_water = 1.0
    worst_drawdown = 0.0
    underwater = 0
    longest_completed = 0
    for value in returns:
        wealth *= 1.0 + float(value)
        high_water = max(high_water, wealth)
        drawdown = wealth / high_water - 1.0
        worst_drawdown = min(worst_drawdown, drawdown)
        if drawdown < 0:
            underwater += 1
        else:
            longest_completed = max(longest_completed, underwater)
            underwater = 0
    return {
        "total_return": wealth - 1.0,
        "max_drawdown": worst_drawdown,
        "longest_completed_underwater_state_days": longest_completed,
        "right_censored_underwater": underwater > 0,
        "terminal_underwater_state_days": underwater,
    }


def market_regime_analysis(
    history: pd.DataFrame,
    daily: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    regime = history[(history["session_date"] >= START) & (history["session_date"] < END)].copy()
    regime = regime[regime["trend_state"] != "UNCLASSIFIED"].reset_index(drop=True)
    if regime.empty:
        raise AssertionError("no classified Stage 9 sessions")
    regime["trend_episode_id"] = episode_ids(regime["trend_state"].tolist())
    regime["vol_episode_id"] = episode_ids(regime["vol_state"].tolist())
    regime["combined_episode_id"] = episode_ids(regime["combined_state"].tolist())

    pivot_columns = ["nav_cny", "daily_return", "drawdown", "equity_weight", "shares"]
    wide = daily.pivot(index="session_date", columns="account_id", values=pivot_columns)
    wide.columns = [f"{metric}__{account}" for metric, account in wide.columns]
    wide = wide.reset_index()
    regime = regime.merge(wide, on="session_date", how="left", validate="one_to_one")
    if regime[f"nav_cny__HD-ANCHOR-001"].isna().any():
        raise AssertionError("market states and P00 daily ledger are not date-aligned")
    fill_map = outcomes[outcomes["status"].isin(["FILLED", "PARTIAL_FILL"])].groupby(
        "session_date"
    ).agg(
        filled_parent_orders=("order_id", "count"),
        filled_buy_orders=("side", lambda values: int((values == "BUY").sum())),
        filled_sell_orders=("side", lambda values: int((values == "SELL").sum())),
    ).reset_index()
    regime = regime.merge(fill_map, on="session_date", how="left")
    for column in ("filled_parent_orders", "filled_buy_orders", "filled_sell_orders"):
        regime[column] = regime[column].fillna(0).astype(int)

    summary_rows: list[dict[str, object]] = []
    episode_rows: list[dict[str, object]] = []
    grouping_specs = (
        ("TREND", "trend_state", "trend_episode_id"),
        ("VOLATILITY", "vol_state", "vol_episode_id"),
        ("COMBINED", "combined_state", "combined_episode_id"),
    )
    for group_type, label_column, episode_column in grouping_specs:
        for label, label_rows in regime.groupby(label_column, sort=True):
            group_episode_ids = label_rows[episode_column].unique().tolist()
            durations = [int((label_rows[episode_column] == item).sum()) for item in group_episode_ids]
            for account_id in ACCOUNT_IDS:
                return_column = f"daily_return__{account_id}"
                valid_returns = label_rows[return_column].dropna().astype(float)
                gross = float((1.0 + valid_returns).prod()) if len(valid_returns) else 1.0
                volatility = float(valid_returns.std(ddof=1) * math.sqrt(252)) if len(valid_returns) > 1 else None
                annualized = gross ** (252.0 / len(valid_returns)) - 1.0 if len(valid_returns) else None
                sharpe = (
                    float(valid_returns.mean() / valid_returns.std(ddof=1) * math.sqrt(252))
                    if len(valid_returns) > 1 and valid_returns.std(ddof=1) > 0 else None
                )
                episode_stats: list[dict[str, object]] = []
                for episode_id in group_episode_ids:
                    episode = label_rows[label_rows[episode_column] == episode_id]
                    values = episode[return_column].dropna().astype(float).tolist()
                    stats = episode_path_stats(values)
                    episode_stats.append(stats)
                    episode_rows.append({
                        "group_type": group_type,
                        "state": label,
                        "episode_id": int(episode_id),
                        "account_id": account_id,
                        "start_date": episode.iloc[0]["session_date"].isoformat(),
                        "end_date": episode.iloc[-1]["session_date"].isoformat(),
                        "duration_trading_sessions": len(episode),
                        **stats,
                    })
                summary_rows.append({
                    "group_type": group_type,
                    "state": label,
                    "account_id": account_id,
                    "classified_sessions": len(label_rows),
                    "performance_sessions": len(valid_returns),
                    "share_of_classified_sessions": len(label_rows) / len(regime),
                    "episodes": len(group_episode_ids),
                    "median_episode_sessions": float(statistics.median(durations)),
                    "maximum_episode_sessions": max(durations),
                    "compounded_return_on_state_days": gross - 1.0,
                    "annualized_equivalent_return": annualized,
                    "annualized_volatility": volatility,
                    "descriptive_sharpe_zero_hurdle": sharpe,
                    "mean_shares": float(label_rows[f"shares__{account_id}"].mean()),
                    "mean_equity_weight": float(label_rows[f"equity_weight__{account_id}"].mean()),
                    "worst_full_path_drawdown_observed": float(
                        label_rows[f"drawdown__{account_id}"].min()
                    ),
                    "worst_within_episode_drawdown": min(
                        float(item["max_drawdown"]) for item in episode_stats
                    ),
                    "worst_completed_underwater_state_days": max(
                        int(item["longest_completed_underwater_state_days"])
                        for item in episode_stats
                    ),
                    "right_censored_underwater_episodes": sum(
                        bool(item["right_censored_underwater"]) for item in episode_stats
                    ),
                    "p00_filled_parent_orders_on_state_days": int(
                        label_rows["filled_parent_orders"].sum()
                    ),
                    "p00_buy_orders_on_state_days": int(label_rows["filled_buy_orders"].sum()),
                    "p00_sell_orders_on_state_days": int(label_rows["filled_sell_orders"].sum()),
                })
    summary = pd.DataFrame(summary_rows)
    episodes = pd.DataFrame(episode_rows)

    trend_pivot = summary[summary["group_type"] == "TREND"].pivot(
        index="state", columns="account_id", values="compounded_return_on_state_days"
    )
    trend_increment = {
        state: float(row["HD-ANCHOR-001"] - row["HD-BASE-RM-001"])
        for state, row in trend_pivot.iterrows()
    }
    overview = {
        "classified_trading_sessions": len(regime),
        "trend_state_counts": {
            str(key): int(value) for key, value in regime["trend_state"].value_counts().items()
        },
        "trend_episode_counts": {
            str(key): int(value)
            for key, value in regime.groupby("trend_state")["trend_episode_id"].nunique().items()
        },
        "high_vol_sessions": int(regime["high_vol"].sum()),
        "high_vol_fraction": float(regime["high_vol"].mean()),
        "trend_dynamic_minus_risk_matched_compounded_return": trend_increment,
        "inference_status": "DESCRIPTIVE_CASE_STUDY_NO_NEW_CONFIRMATORY_INTERVAL",
    }
    return regime, summary, episodes, overview


def load_pit() -> pd.DataFrame:
    pit = pd.read_csv(PIT, encoding="utf-8-sig")
    for column in ("available_time", "effective_time", "expiry_time", "superseded_time"):
        pit[column] = pit[column].apply(parse_dt)
    pit["expected_annual_dividend_per_share"] = pd.to_numeric(
        pit["expected_annual_dividend_per_share"]
    )
    pit = pit.sort_values("available_time").reset_index(drop=True)
    return pit


def dividend_reliability(
    pit: pd.DataFrame,
    signals: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    rows: list[dict[str, object]] = []
    relevant = pit[
        (pit["available_time"].apply(lambda value: value.date()) < END)
        & (pit["expiry_time"].apply(lambda value: value.date()) >= START)
    ].copy()
    previous_dps: float | None = None
    for _, item in relevant.iterrows():
        effective_end = min(
            value for value in (item["expiry_time"], item["superseded_time"]) if value is not None
        )
        change = None if previous_dps is None else float(item["expected_annual_dividend_per_share"] - previous_dps)
        pct = None if previous_dps in (None, 0) else change / previous_dps
        rows.append({
            "record_id": item["record_id"],
            "available_time": item["available_time"].isoformat(),
            "expiry_time": item["expiry_time"].isoformat(),
            "superseded_time": item["superseded_time"].isoformat() if item["superseded_time"] else None,
            "effective_end": effective_end.isoformat(),
            "effective_calendar_days": (effective_end - item["available_time"]).days,
            "dps_cny": float(item["expected_annual_dividend_per_share"]),
            "change_cny": change,
            "change_fraction": pct,
            "direction": None if change is None else "UP" if change > 0 else "DOWN" if change < 0 else "UNCHANGED",
        })
        previous_dps = float(item["expected_annual_dividend_per_share"])
    frame = pd.DataFrame(rows)

    order_to_signal = signals[signals["generated_order_id"].notna()].set_index("generated_order_id")
    buy_checks: list[dict[str, object]] = []
    for _, fill in outcomes[(outcomes["status"] == "FILLED") & (outcomes["side"] == "BUY")].iterrows():
        signal = order_to_signal.loc[fill["order_id"]]
        fill_date = fill["session_date"]
        current_id = signal["selected_pit_record_id"]
        current_dps = float(pit.set_index("record_id").loc[current_id, "expected_annual_dividend_per_share"])
        deadline = fill_date + timedelta(days=180)
        later = pit[
            (pit["available_time"].apply(lambda value: value.date()) > fill_date)
            & (pit["available_time"].apply(lambda value: value.date()) <= deadline)
            & (pit["available_time"].apply(lambda value: value.date()) < END)
        ]
        downward = later[later["expected_annual_dividend_per_share"] < current_dps]
        first = downward.iloc[0] if not downward.empty else None
        buy_checks.append({
            "order_id": fill["order_id"],
            "fill_date": fill_date.isoformat(),
            "selected_pit_record_id": current_id,
            "selected_dps_cny": current_dps,
            "downward_revision_within_180_calendar_days": first is not None,
            "first_downward_revision_record_id": None if first is None else first["record_id"],
            "first_downward_revision_available_time": None if first is None else first["available_time"].isoformat(),
        })
    downward_count = sum(item["downward_revision_within_180_calendar_days"] for item in buy_checks)
    summary = {
        "relevant_pit_records": len(frame),
        "revisions_after_first": max(len(frame) - 1, 0),
        "upward_revisions": int((frame["direction"] == "UP").sum()),
        "downward_revisions": int((frame["direction"] == "DOWN").sum()),
        "expired_before_superseded_records": int(
            sum(parse_dt(item["expiry_time"]) < parse_dt(item["superseded_time"]) for item in rows)
        ),
        "buy_fills": len(buy_checks),
        "buy_fills_followed_by_downward_revision_within_180_days": downward_count,
        "buy_fill_revision_checks": buy_checks,
    }
    return frame, summary


def selected_dps_by_record(pit: pd.DataFrame) -> dict[str, float]:
    return {
        str(item["record_id"]): float(item["expected_annual_dividend_per_share"])
        for _, item in pit.iterrows()
    }


def anchor_repair(
    history: pd.DataFrame,
    pit: pd.DataFrame,
    signals: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    trading = history.reset_index(drop=True)
    index_by_date = {item["session_date"]: index for index, item in trading.iterrows()}
    signal_by_date = signals.set_index("session_date")
    dps_lookup = selected_dps_by_record(pit)
    buys = signals[
        signals["generated_order_id"].notna() & (signals["order_reason"] == "ADJACENT_BUY")
    ].sort_values("session_date")
    buy_dates = buys["session_date"].tolist()
    rows: list[dict[str, object]] = []
    for _, item in buys.iterrows():
        start_date = item["session_date"]
        start_index = index_by_date[start_date]
        end_index = start_index + 63
        start_price = float(item["decision_close_cny"])
        start_dps = float(item["decision_dps_cny"])
        start_anchor = start_dps / 0.035
        base = {
            "order_id": item["generated_order_id"],
            "signal_date": start_date.isoformat(),
            "start_close_cny": start_price,
            "start_dps_cny": start_dps,
            "start_anchor_3_5pct_cny": start_anchor,
            "start_price_to_anchor_gap": start_price / start_anchor - 1.0,
            "overlapping_buy_within_63_sessions": any(
                start_index < index_by_date[other] <= end_index
                for other in buy_dates if other in index_by_date
            ),
        }
        if end_index >= len(trading) or trading.iloc[end_index]["session_date"] >= END:
            base.update({
                "status": "RIGHT_CENSORED_FEWER_THAN_63_LATER_TRADING_SESSIONS",
                "end_date": None,
            })
            rows.append(base)
            continue
        end_item = trading.iloc[end_index]
        end_date = end_item["session_date"]
        end_signal = signal_by_date.loc[end_date]
        end_record_id = end_signal["selected_pit_record_id"]
        end_dps = dps_lookup[str(end_record_id)]
        end_price = float(end_signal["decision_close_cny"])
        end_anchor = end_dps / 0.035
        end_gap = end_price / end_anchor - 1.0
        start_tri = float(trading.iloc[start_index]["total_return_index"])
        end_tri = float(end_item["total_return_index"])
        base.update({
            "status": "MATURE_63_TRADING_SESSIONS",
            "end_date": end_date.isoformat(),
            "end_close_cny": end_price,
            "end_pit_record_id": end_record_id,
            "end_dps_cny": end_dps,
            "end_anchor_3_5pct_cny": end_anchor,
            "end_price_to_anchor_gap": end_gap,
            "price_return": end_price / start_price - 1.0,
            "underlying_total_return": end_tri / start_tri - 1.0,
            "dps_change_fraction": end_dps / start_dps - 1.0,
            "absolute_anchor_gap_change": abs(end_gap) - abs(base["start_price_to_anchor_gap"]),
            "anchor_gap_repaired": abs(end_gap) < abs(base["start_price_to_anchor_gap"]),
        })
        rows.append(base)
    frame = pd.DataFrame(rows)
    mature = frame[frame["status"] == "MATURE_63_TRADING_SESSIONS"]
    summary = {
        "buy_signals": len(frame),
        "mature_63_session_events": len(mature),
        "right_censored_events": int((frame["status"] != "MATURE_63_TRADING_SESSIONS").sum()),
        "overlapping_events": int(frame["overlapping_buy_within_63_sessions"].sum()),
        "anchor_gap_repaired_events": int(mature["anchor_gap_repaired"].sum()),
        "positive_underlying_total_return_events": int((mature["underlying_total_return"] > 0).sum()),
        "inference_status": "CASE_STUDY_OVERLAPPING_LOW_EVENT_COUNT",
    }
    return frame, summary


def signal_fill_diagnostics(
    signals: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    generated = signals[signals["generated_order_id"].notna()][
        ["generated_order_id", "session_date", "decision_close_cny", "order_reason"]
    ].rename(columns={
        "generated_order_id": "order_id",
        "session_date": "signal_date",
    })
    merged = outcomes.merge(generated, on="order_id", how="left", validate="one_to_one")
    merged["decision_close_cny"] = pd.to_numeric(merged["decision_close_cny"])
    merged["adverse_bps_signal_close_to_fill"] = merged.apply(
        lambda item: (
            (item["fill_price_cny"] / item["decision_close_cny"] - 1.0) * 10000
            if item["side"] == "BUY" else
            (item["decision_close_cny"] / item["fill_price_cny"] - 1.0) * 10000
        ) if item["status"] in ("FILLED", "PARTIAL_FILL") else None,
        axis=1,
    )
    columns = [
        "order_id", "signal_date", "session_date", "side", "order_reason", "status", "reason",
        "decision_close_cny", "fill_price_cny", "requested_quantity", "filled_quantity",
        "adverse_bps_signal_close_to_fill", "total_fees_cny", "deferred_tax_paid_cny",
    ]
    frame = merged[columns].copy()
    valid = frame["adverse_bps_signal_close_to_fill"].notna()
    summary = {
        "generated_parent_orders": len(generated),
        "filled_parent_orders": int((frame["status"] == "FILLED").sum()),
        "partial_parent_orders": int((frame["status"] == "PARTIAL_FILL").sum()),
        "unfilled_parent_orders": int((frame["status"] == "UNFILLED").sum()),
        "mean_adverse_bps_signal_close_to_fill": float(
            frame.loc[valid, "adverse_bps_signal_close_to_fill"].mean()
        ),
        "median_adverse_bps_signal_close_to_fill": float(
            frame.loc[valid, "adverse_bps_signal_close_to_fill"].median()
        ),
        "worst_adverse_bps_signal_close_to_fill": float(
            frame.loc[valid, "adverse_bps_signal_close_to_fill"].max()
        ),
        "model_reference_minus_fill_bps": 0.0,
        "model_note": "P00 fill equals the frozen T+1 official close reference by construction; signal-close-to-fill movement remains real next-session price movement.",
    }
    return frame, summary


def trade_batch_attribution(
    actions: Sequence[object],
    daily: pd.DataFrame,
    outcomes: pd.DataFrame,
    formal_result: Mapping[str, object],
) -> tuple[pd.DataFrame, dict[str, object]]:
    fills = outcomes[outcomes["status"] == "FILLED"].sort_values("session_index")
    lots: list[dict[str, object]] = []
    open_lots: list[dict[str, object]] = []
    for _, fill in fills.iterrows():
        if fill["side"] == "BUY":
            lot = {
                "batch_id": f"BATCH-{len(lots) + 1:02d}",
                "buy_order_id": fill["order_id"],
                "buy_date": fill["session_date"],
                "shares": int(fill["filled_quantity"]),
                "buy_price_cny": float(fill["fill_price_cny"]),
                "buy_fees_cny": float(fill["total_fees_cny"]),
                "sell_order_id": None,
                "sell_date": None,
                "sell_price_cny": None,
                "sell_fees_cny": 0.0,
                "deferred_tax_paid_cny": 0.0,
            }
            lots.append(lot)
            open_lots.append(lot)
        elif fill["side"] == "SELL":
            remaining = int(fill["filled_quantity"])
            if not open_lots:
                raise AssertionError("dynamic-layer FIFO attribution has no open batch")
            while remaining:
                lot = open_lots[0]
                available = int(lot["shares"])
                matched = min(remaining, available)
                if matched != available:
                    raise AssertionError("partial dynamic batch matching is not implemented")
                fraction = matched / int(fill["filled_quantity"])
                lot["sell_order_id"] = fill["order_id"]
                lot["sell_date"] = fill["session_date"]
                lot["sell_price_cny"] = float(fill["fill_price_cny"])
                lot["sell_fees_cny"] = float(fill["total_fees_cny"]) * fraction
                lot["deferred_tax_paid_cny"] = float(fill["deferred_tax_paid_cny"]) * fraction
                open_lots.pop(0)
                remaining -= matched

    p00 = daily[daily["account_id"] == "HD-ANCHOR-001"].sort_values("session_date")
    terminal = p00.iloc[-1]
    terminal_mark = float(terminal["mark_cny"])
    terminal_date = terminal["session_date"]
    terminal_tax = float(terminal.get("tax_liability_cny", 0) or 0)
    if terminal_tax != 0:
        raise AssertionError("non-zero terminal tax liability requires explicit batch allocation")

    rows: list[dict[str, object]] = []
    eligible_actions = [action for action in actions if START <= action.record_date < END]
    for lot in lots:
        sell_date = lot["sell_date"]
        entitled = [
            action for action in eligible_actions
            if lot["buy_date"] <= action.record_date
            and (sell_date is None or action.record_date < sell_date)
        ]
        dividends = sum(float(action.cash_dividend_per_share) * int(lot["shares"]) for action in entitled)
        exit_price = terminal_mark if sell_date is None else float(lot["sell_price_cny"])
        exit_value = exit_price * int(lot["shares"])
        buy_cost = float(lot["buy_price_cny"]) * int(lot["shares"])
        contribution = (
            exit_value + dividends - buy_cost - float(lot["buy_fees_cny"])
            - float(lot["sell_fees_cny"]) - float(lot["deferred_tax_paid_cny"])
        )
        rows.append({
            **{key: value.isoformat() if isinstance(value, date) else value for key, value in lot.items()},
            "status": "OPEN_MARKED_AT_TERMINAL" if sell_date is None else "CLOSED_LOGICAL_DYNAMIC_BATCH",
            "exit_or_mark_date": terminal_date.isoformat() if sell_date is None else sell_date.isoformat(),
            "exit_or_mark_price_cny": exit_price,
            "gross_dividend_entitlements_cny": dividends,
            "dividend_action_ids": "|".join(action.action_id for action in entitled),
            "net_contribution_cny": contribution,
        })
    frame = pd.DataFrame(rows)
    largest = frame.loc[frame["net_contribution_cny"].idxmax()]
    terminal_increment = float(
        formal_result["primary_result"]["p00_vs_risk_matched"]["terminal_asset_difference_cny"]
    )
    remaining = terminal_increment - float(largest["net_contribution_cny"])
    summary = {
        "dynamic_buy_batches": len(frame),
        "closed_logical_batches": int((frame["status"] == "CLOSED_LOGICAL_DYNAMIC_BATCH").sum()),
        "terminal_open_logical_batches": int((frame["status"] == "OPEN_MARKED_AT_TERMINAL").sum()),
        "largest_positive_batch_id": str(largest["batch_id"]),
        "largest_positive_batch_contribution_cny": float(largest["net_contribution_cny"]),
        "frozen_terminal_asset_increment_vs_rm_cny": terminal_increment,
        "remaining_terminal_asset_increment_after_subtraction_cny": remaining,
        "remaining_total_return_increment_after_subtraction": remaining / 60000.0,
        "exclude_best_trade_gate": "PASS" if remaining >= 0 else "FAIL",
        "attribution_scope": "Logical dynamic 100-share layers only; the initial structural 100-share difference versus the 900-share comparator and all residual interaction terms remain fixed and are not allocated here.",
        "reconciliation_claim": "NOT_A_COMPLETE_STAGE10_RETURN_ATTRIBUTION",
    }
    return frame, summary


def execute() -> dict[str, object]:
    if OUTPUT_DIR.exists() or RESULT.exists():
        raise FileExistsError("Stage 9 output already exists; immutable artifacts will not be overwritten")
    input_checks = validate_frozen_inputs()
    formal_result = json_load(FORMAL_RESULT)
    if formal_result["locked_period_status"] != "NOT_OPENED_NOT_READ":
        raise AssertionError("historical pseudo-lock is no longer closed")

    profile_frame, profile_summary = profile_robustness()
    history = load_total_return_history()
    daily, signals, outcomes = load_p00_ledgers()
    regime_daily, regime_summary, regime_episodes, regime_overview = market_regime_analysis(
        history, daily, outcomes
    )
    pit = load_pit()
    dividend_frame, dividend_summary = dividend_reliability(pit, signals, outcomes)
    anchor_frame, anchor_summary = anchor_repair(history, pit, signals)
    signal_fill_frame, signal_fill_summary = signal_fill_diagnostics(signals, outcomes)
    actions = [action for action in load_corporate_actions(ACTIONS) if action.ex_date < END]
    batch_frame, batch_summary = trade_batch_attribution(
        actions, daily, outcomes, formal_result
    )

    annual = json_load(FORMAL_DIR / "profile_results.json")["P00"][
        "annual_relative_diagnostics_vs_rm"
    ]
    exclude_year_value = float(
        annual["exclude_largest_relative_year_remaining_total_return_increment"]
    )
    gates = {
        "required_registered_stress_profiles_nonnegative": profile_summary[
            "required_profiles_nonnegative_gate"
        ],
        "local_parameter_neighbors_at_least_3_of_4_nonnegative": profile_summary[
            "local_neighbor_gate"
        ],
        "exclude_largest_relative_year_remaining_increment_nonnegative": (
            "PASS" if exclude_year_value >= 0 else "FAIL"
        ),
        "exclude_largest_dynamic_batch_remaining_increment_nonnegative": batch_summary[
            "exclude_best_trade_gate"
        ],
        "P21_cash_yield": "NOT_RUN_NO_AUDITABLE_EXECUTABLE_BROKER_CASH_RATE_INPUT",
        "P22_P23_execution_interruption": "NOT_ACTIVATED_FEWER_THAN_10_OTHERWISE_FILLABLE_PARENT_ORDERS",
        "market_state_analysis": "COMPLETE_DESCRIPTIVE_CASE_STUDY",
        "M1_dividend_reliability": "COMPLETE_LOW_EVENT_COUNT",
        "M2_anchor_repair": "COMPLETE_OVERLAPPING_LOW_EVENT_COUNT",
        "historical_pseudo_lock": "NOT_OPENED_NOT_READ",
        "prospective_clean_L3": "NOT_YET_AVAILABLE",
    }

    details = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE9-READONLY-DETAILS-1.0-PRELOCK",
        "authorized_scope": "[2022-03-10, 2025-09-10)",
        "profile_robustness": profile_summary,
        "market_regimes": regime_overview,
        "dividend_reliability": dividend_summary,
        "anchor_repair": anchor_summary,
        "signal_to_fill": signal_fill_summary,
        "trade_batch_attribution_stress": batch_summary,
        "exclude_largest_relative_year": annual,
        "gates": gates,
        "limitations": [
            "All outputs are derived from already-viewed retrospective L2 paths; no L3 upgrade is possible.",
            "Market-state returns are descriptive conditional subsets, not new executable strategy paths or confirmatory tests.",
            "Regime episodes and state transitions are sparse; no new state-conditioned confidence interval is asserted.",
            "The best-batch subtraction is a fixed-path attribution stress and does not replace Stage 10 full accounting attribution.",
        ],
    }

    temp_parent = Path(tempfile.mkdtemp(prefix="stage9_tmp_", dir=EXPERIMENT))
    try:
        profile_frame.to_csv(temp_parent / "profile_robustness.csv", index=False, encoding="utf-8")
        regime_daily.to_parquet(temp_parent / "market_regime_daily.parquet", index=False)
        regime_summary.to_csv(temp_parent / "market_regime_summary.csv", index=False, encoding="utf-8")
        regime_episodes.to_csv(temp_parent / "market_regime_episodes.csv", index=False, encoding="utf-8")
        dividend_frame.to_csv(temp_parent / "dividend_reliability.csv", index=False, encoding="utf-8")
        anchor_frame.to_csv(temp_parent / "anchor_repair.csv", index=False, encoding="utf-8")
        signal_fill_frame.to_csv(temp_parent / "signal_fill_diagnostics.csv", index=False, encoding="utf-8")
        batch_frame.to_csv(temp_parent / "trade_batch_attribution.csv", index=False, encoding="utf-8")
        write_json(temp_parent / "stage9_details.json", details)
        os.replace(temp_parent, OUTPUT_DIR)
    except Exception:
        shutil.rmtree(temp_parent, ignore_errors=True)
        raise

    result = {
        "statement_type": "计算结果",
        "experiment_id": "HD-ANCHOR-001",
        "artifact_version": "HD-STAGE9-READONLY-RESULT-1.0-PRELOCK",
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "status": "PASS_STAGE9_READONLY_ROBUSTNESS_AND_FALSIFICATION_COMPLETE",
        "authorized_scope": "[2022-03-10, 2025-09-10)",
        "strategy_run_count_increment": 0,
        "performance_path_calculation_count_increment": 0,
        "historical_pseudo_lock_open_count_increment": 0,
        "input_checks": input_checks,
        "output_rows": {
            "profile_robustness": len(profile_frame),
            "market_regime_daily": len(regime_daily),
            "market_regime_summary": len(regime_summary),
            "market_regime_episodes": len(regime_episodes),
            "dividend_reliability": len(dividend_frame),
            "anchor_repair": len(anchor_frame),
            "signal_fill_diagnostics": len(signal_fill_frame),
            "trade_batch_attribution": len(batch_frame),
        },
        "robustness": {
            **profile_summary,
            "exclude_largest_relative_year": int(annual["largest_positive_relative_year"]),
            "exclude_largest_relative_year_remaining_total_return_increment": exclude_year_value,
            "exclude_largest_dynamic_batch": batch_summary,
        },
        "market_regimes": regime_overview,
        "mechanisms": {
            "dividend_reliability": dividend_summary,
            "anchor_repair": anchor_summary,
            "signal_to_fill": signal_fill_summary,
        },
        "gates": gates,
        "research_decision": "修改",
        "decision_reason": "STAGE8_PERSONAL_RISK_AND_RECOVERY_FAILURES_REMAIN;_STAGE9_DOES_NOT_CURE_RISK_MISMATCH_EVENT_INSUFFICIENCY_OR_CI_CROSSING_ZERO",
        "evidence_ceiling": "L2_RETROSPECTIVE",
        "historical_pseudo_lock_status": "NOT_OPENED_NOT_READ",
        "next_gate": "STAGE10_FULL_RETURN_ATTRIBUTION_USING_THE_SAME_FROZEN_LEDGER_WITHOUT_RERUNNING_THE_STRATEGY",
    }
    write_json(RESULT, result)
    return result


if __name__ == "__main__":
    print(json.dumps(execute(), ensure_ascii=False, indent=2))
