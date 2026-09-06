#!/usr/bin/env python3
"""Compute retrospective risk windows for 600900.SH from two adjusted-price APIs.

This is a descriptive underlying-price diagnostic. It does not run HD-ANCHOR-001,
open a locked test set, or create trading orders. The script writes JSON to stdout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable


EASTMONEY_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_DIVIDEND_ENDPOINT = "https://datacenter-web.eastmoney.com/api/data/v1/get"
YAHOO_ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/600900.SS"
WINDOWS = (
    ("3个月", 0, 3),
    ("6个月", 0, 6),
    ("1年", 1, 0),
    ("3年", 3, 0),
    ("5年", 5, 0),
    ("10年", 10, 0),
)


@dataclass(frozen=True)
class Point:
    date: dt.date
    close: float


def get_json(url: str, params: dict[str, str], *, attempts: int = 3) -> dict:
    request_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        request_url,
        headers={"User-Agent": "Mozilla/5.0 HD-ANCHOR-001 research audit"},
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (OSError, TimeoutError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt)
    assert last_error is not None
    raise last_error


def fetch_eastmoney_prices() -> tuple[list[Point], str]:
    params = {
        "secid": "1.600900",
        "klt": "101",
        "fqt": "0",
        "lmt": "10000",
        "end": "20500101",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    payload = get_json(EASTMONEY_ENDPOINT, params)
    rows = payload["data"]["klines"]
    points = []
    for row in rows:
        fields = row.split(",")
        points.append(Point(dt.date.fromisoformat(fields[0]), float(fields[2])))
    return points, f"{EASTMONEY_ENDPOINT}?{urllib.parse.urlencode(params)}"


def fetch_eastmoney_dividends() -> tuple[dict[dt.date, float], list[dt.date], str]:
    params = {
        "reportName": "RPT_SHAREBONUS_DET",
        "columns": "ALL",
        "filter": '(SECURITY_CODE="600900")',
        "pageSize": "50",
        "pageNumber": "1",
        "sortColumns": "EX_DIVIDEND_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    payload = get_json(EASTMONEY_DIVIDEND_ENDPOINT, params)
    events: dict[dt.date, float] = {}
    share_action_dates: list[dt.date] = []
    for row in payload["result"]["data"]:
        if row["EX_DIVIDEND_DATE"] is None:
            continue
        date = dt.date.fromisoformat(row["EX_DIVIDEND_DATE"][:10])
        if any(row.get(field) not in (None, 0, 0.0) for field in ("BONUS_IT_RATIO", "BONUS_RATIO", "IT_RATIO")):
            share_action_dates.append(date)
        if row["PRETAX_BONUS_RMB"] is None:
            continue
        # The endpoint reports PRETAX_BONUS_RMB as yuan per 10 shares.
        amount_per_share = float(row["PRETAX_BONUS_RMB"]) / 10.0
        events[date] = events.get(date, 0.0) + amount_per_share
    return events, share_action_dates, f"{EASTMONEY_DIVIDEND_ENDPOINT}?{urllib.parse.urlencode(params)}"


def fetch_yahoo(
    start: dt.date, end_exclusive: dt.date
) -> tuple[list[Point], dict[dt.date, float], str]:
    utc = dt.timezone.utc
    period1 = int(dt.datetime.combine(start, dt.time.min, utc).timestamp())
    period2 = int(dt.datetime.combine(end_exclusive, dt.time.min, utc).timestamp())
    params = {
        "period1": str(period1),
        "period2": str(period2),
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    payload = get_json(YAHOO_ENDPOINT, params)
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    raw_closes = result["indicators"]["quote"][0]["close"]
    points = []
    for timestamp, close in zip(timestamps, raw_closes):
        if close is None:
            continue
        date = dt.datetime.fromtimestamp(timestamp, tz=utc).date()
        points.append(Point(date, float(close)))
    events = result.get("events", {})
    if events.get("splits"):
        raise ValueError("Yahoo reports a split; an explicit split rule is required")
    dividends: dict[dt.date, float] = {}
    for event in events.get("dividends", {}).values():
        date = dt.datetime.fromtimestamp(event["date"], tz=utc).date()
        dividends[date] = dividends.get(date, 0.0) + float(event["amount"])
    return points, dividends, f"{YAHOO_ENDPOINT}?{urllib.parse.urlencode(params)}"


def shift_date(date: dt.date, *, years: int = 0, months: int = 0) -> dt.date:
    target_month = date.month - months
    year = date.year - years
    while target_month <= 0:
        target_month += 12
        year -= 1
    month_lengths = (31, 29 if _is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return dt.date(year, target_month, min(date.day, month_lengths[target_month - 1]))


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def series_hash(points: Iterable[Point]) -> str:
    canonical = "".join(f"{p.date.isoformat()},{p.close:.10f}\n" for p in points)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def event_hash(events: dict[dt.date, float]) -> str:
    canonical = "".join(f"{date.isoformat()},{events[date]:.10f}\n" for date in sorted(events))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def total_return_index(points: list[Point], dividends: dict[dt.date, float]) -> list[Point]:
    if not points:
        raise ValueError("empty price series")
    output = [Point(points[0].date, 100.0)]
    previous_close = points[0].close
    for point in points[1:]:
        if previous_close <= 0 or point.close <= 0:
            raise ValueError("non-positive raw close")
        gross_return = (point.close + dividends.get(point.date, 0.0)) / previous_close
        output.append(Point(point.date, output[-1].close * gross_return))
        previous_close = point.close
    return output


def trading_day_gap(points: list[Point], start_index: int, end_index: int) -> int:
    return end_index - start_index


def metrics(points: list[Point], cutoff: dt.date) -> dict:
    sample = [point for point in points if point.date >= cutoff]
    if len(sample) < 2:
        raise ValueError(f"not enough points on/after {cutoff}")
    if any(point.close <= 0 for point in sample):
        raise ValueError(f"non-positive adjusted close in window beginning {cutoff}")

    log_returns = [math.log(sample[i].close / sample[i - 1].close) for i in range(1, len(sample))]
    annualized_volatility = statistics.stdev(log_returns) * math.sqrt(252)

    running_peak = sample[0].close
    running_peak_index = 0
    max_drawdown = 0.0
    peak_index = 0
    trough_index = 0
    for index, point in enumerate(sample):
        if point.close > running_peak:
            running_peak = point.close
            running_peak_index = index
        drawdown = point.close / running_peak - 1.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            peak_index = running_peak_index
            trough_index = index

    recovery_index = None
    peak_close = sample[peak_index].close
    for index in range(trough_index + 1, len(sample)):
        if sample[index].close >= peak_close:
            recovery_index = index
            break

    if recovery_index is None:
        endpoint_index = len(sample) - 1
        recovery = {
            "status": "UNRECOVERED_RIGHT_CENSORED",
            "date": None,
            "peak_to_recovery_trading_days": None,
            "peak_to_recovery_calendar_days": None,
            "trough_to_recovery_trading_days": None,
            "trough_to_recovery_calendar_days": None,
            "peak_to_cutoff_trading_days": trading_day_gap(sample, peak_index, endpoint_index),
            "peak_to_cutoff_calendar_days": (sample[endpoint_index].date - sample[peak_index].date).days,
            "trough_to_cutoff_trading_days": trading_day_gap(sample, trough_index, endpoint_index),
            "trough_to_cutoff_calendar_days": (sample[endpoint_index].date - sample[trough_index].date).days,
        }
    else:
        recovery = {
            "status": "RECOVERED",
            "date": sample[recovery_index].date.isoformat(),
            "peak_to_recovery_trading_days": trading_day_gap(sample, peak_index, recovery_index),
            "peak_to_recovery_calendar_days": (sample[recovery_index].date - sample[peak_index].date).days,
            "trough_to_recovery_trading_days": trading_day_gap(sample, trough_index, recovery_index),
            "trough_to_recovery_calendar_days": (sample[recovery_index].date - sample[trough_index].date).days,
            "peak_to_cutoff_trading_days": None,
            "peak_to_cutoff_calendar_days": None,
            "trough_to_cutoff_trading_days": None,
            "trough_to_cutoff_calendar_days": None,
        }

    return {
        "requested_cutoff": cutoff.isoformat(),
        "actual_start": sample[0].date.isoformat(),
        "end": sample[-1].date.isoformat(),
        "price_observations": len(sample),
        "return_observations": len(log_returns),
        "annualized_log_return_volatility": annualized_volatility,
        "max_drawdown": max_drawdown,
        "peak_date": sample[peak_index].date.isoformat(),
        "peak_adjusted_close": peak_close,
        "trough_date": sample[trough_index].date.isoformat(),
        "trough_adjusted_close": sample[trough_index].close,
        "recovery": recovery,
    }


def common_price_check(eastmoney: list[Point], yahoo: list[Point], cutoff: dt.date) -> dict:
    east = {point.date: point.close for point in eastmoney if point.date >= cutoff}
    other = {point.date: point.close for point in yahoo if point.date >= cutoff}
    dates = sorted(east.keys() & other.keys())
    close_differences = []
    return_differences = []
    for date in dates:
        close_differences.append(abs(east[date] - other[date]))
    for previous, current in zip(dates, dates[1:]):
        east_return = east[current] / east[previous] - 1.0
        other_return = other[current] / other[previous] - 1.0
        return_differences.append(abs(east_return - other_return))
    return {
        "common_price_dates": len(dates),
        "common_return_intervals": len(return_differences),
        "mean_absolute_raw_close_difference_cny": statistics.mean(close_differences),
        "max_absolute_raw_close_difference_cny": max(close_differences),
        "mean_absolute_daily_return_difference": statistics.mean(return_differences),
        "max_absolute_daily_return_difference": max(return_differences),
        "intervals_difference_over_1bp": sum(value > 0.0001 for value in return_differences),
        "intervals_difference_over_10bp": sum(value > 0.001 for value in return_differences),
        "intervals_difference_over_1pct_point": sum(value > 0.01 for value in return_differences),
    }


def dividend_check(
    eastmoney: dict[dt.date, float], yahoo: dict[dt.date, float], cutoff: dt.date
) -> dict:
    east = {date: amount for date, amount in eastmoney.items() if date >= cutoff}
    other = {date: amount for date, amount in yahoo.items() if date >= cutoff}
    all_dates = sorted(east.keys() | other.keys())
    rows = []
    for date in all_dates:
        east_amount = east.get(date)
        other_amount = other.get(date)
        relative = None
        if east_amount is not None and other_amount is not None and east_amount != 0:
            relative = abs(east_amount - other_amount) / abs(east_amount)
        rows.append(
            {
                "ex_date": date.isoformat(),
                "eastmoney_pretax_cny_per_share": east_amount,
                "yahoo_cny_per_share": other_amount,
                "relative_difference": relative,
            }
        )
    return {
        "event_dates_union": len(all_dates),
        "event_dates_matched": sum(row["eastmoney_pretax_cny_per_share"] is not None and row["yahoo_cny_per_share"] is not None for row in rows),
        "all_matched_amounts_within_1pct": all(
            row["relative_difference"] is not None and row["relative_difference"] <= 0.01 for row in rows
        ),
        "events": rows,
    }


def relative_difference(reference: float, comparison: float) -> float:
    return abs(reference - comparison) / abs(reference) if reference != 0 else math.nan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieved-at", default=dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    args = parser.parse_args()

    eastmoney_prices, eastmoney_price_url = fetch_eastmoney_prices()
    eastmoney_dividends, eastmoney_share_actions, eastmoney_dividend_url = fetch_eastmoney_dividends()
    latest_eastmoney = eastmoney_prices[-1].date
    yahoo_prices, yahoo_dividends, yahoo_url = fetch_yahoo(
        shift_date(latest_eastmoney, years=10, months=1),
        latest_eastmoney + dt.timedelta(days=3),
    )
    common_end = min(latest_eastmoney, yahoo_prices[-1].date)
    common_start = yahoo_prices[0].date
    if any(date >= common_start for date in eastmoney_share_actions):
        raise ValueError("share bonus or capitalization event inside analysis coverage")
    eastmoney_prices = [point for point in eastmoney_prices if common_start <= point.date <= common_end]
    yahoo_prices = [point for point in yahoo_prices if point.date <= common_end]
    eastmoney_total_return = total_return_index(eastmoney_prices, eastmoney_dividends)
    yahoo_total_return = total_return_index(yahoo_prices, yahoo_dividends)
    ten_year_cutoff = shift_date(common_end, years=10)

    output = {
        "metadata": {
            "symbol": "600900.SH / 600900.SS",
            "retrieved_at": args.retrieved_at,
            "common_data_cutoff": common_end.isoformat(),
            "metric_purpose": "retrospective pretax total-return risk profile for the underlying; not strategy performance",
            "volatility": "sample standard deviation of daily tax-free total-return-index log returns multiplied by sqrt(252)",
            "drawdown": "tax-free total-return index divided by the running maximum inside each window, minus one",
            "window": "calendar offset from common cutoff; actual start is first available trading day on or after cutoff",
            "trading_day_gap": "number of close-to-close intervals; peak day to next trading day equals one",
        },
        "sources": {
            "eastmoney": {
                "price": "unadjusted daily close (fqt=0)",
                "dividend": "RPT_SHAREBONUS_DET PRETAX_BONUS_RMB / 10 on EX_DIVIDEND_DATE",
                "price_url": eastmoney_price_url,
                "dividend_url": eastmoney_dividend_url,
                "price_observations": len(eastmoney_prices),
                "first": eastmoney_prices[0].date.isoformat(),
                "last": eastmoney_prices[-1].date.isoformat(),
                "raw_price_series_sha256": series_hash(eastmoney_prices),
                "dividend_events_sha256": event_hash(eastmoney_dividends),
            },
            "yahoo": {
                "price": "raw close",
                "dividend": "chart event amount on event date",
                "url": yahoo_url,
                "price_observations": len(yahoo_prices),
                "first": yahoo_prices[0].date.isoformat(),
                "last": yahoo_prices[-1].date.isoformat(),
                "raw_price_series_sha256": series_hash(yahoo_prices),
                "dividend_events_sha256": event_hash(yahoo_dividends),
            },
        },
        "cross_source_raw_prices_10y": common_price_check(eastmoney_prices, yahoo_prices, ten_year_cutoff),
        "cross_source_dividends_10y": dividend_check(eastmoney_dividends, yahoo_dividends, ten_year_cutoff),
        "windows": {},
    }
    for label, years, months in WINDOWS:
        cutoff = shift_date(common_end, years=years, months=months)
        east_metrics = metrics(eastmoney_total_return, cutoff)
        yahoo_metrics = metrics(yahoo_total_return, cutoff)
        output["windows"][label] = {
            "eastmoney": east_metrics,
            "yahoo": yahoo_metrics,
            "cross_source_relative_difference": {
                "annualized_volatility": relative_difference(
                    east_metrics["annualized_log_return_volatility"],
                    yahoo_metrics["annualized_log_return_volatility"],
                ),
                "absolute_max_drawdown_magnitude": relative_difference(
                    abs(east_metrics["max_drawdown"]), abs(yahoo_metrics["max_drawdown"])
                ),
            },
        }
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
