"""Plot the frozen P00 trade timeline against PIT dividend-anchor price bands.

This is a read-only visualization. It does not call the strategy engine, alter
the frozen ledgers, calculate performance, or open any sealed result. The PIT
selector is reused from the audited Stage 8 engine so that the plotted anchor
lines follow the same availability, expiry, and supersession semantics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


TOPIC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOPIC_ROOT.parents[2]
sys.path.insert(0, str(TOPIC_ROOT))

from engine.stage8_engine import PITDividendSelector, shanghai_close  # noqa: E402


EXPERIMENT_ROOT = TOPIC_ROOT / "experiments" / "HD-ANCHOR-001"
DEFAULT_PRICE = TOPIC_ROOT / "datasets" / "cleaned" / "cleaned_price.csv"
DEFAULT_PIT = (
    TOPIC_ROOT / "datasets" / "cleaned" / "point_in_time_dividend_estimates.csv"
)
DEFAULT_TRADES = (
    EXPERIMENT_ROOT
    / "stage9_readonly_v1.0_prelock"
    / "signal_fill_diagnostics.csv"
)
DEFAULT_OUTPUT = (
    EXPERIMENT_ROOT
    / "readonly_visualizations"
    / "p00_trade_timeline_dividend_anchor_bands_v1.0.png"
)

START_DATE = date(2022, 3, 10)
END_DATE = date(2025, 9, 9)
INITIAL_SHARES = 1000

BANDS = [
    ("4.2% 深度价值", 0.042, "#2166AC"),
    ("4.0% 买入区", 0.040, "#4393C3"),
    ("3.5% 中性区", 0.035, "#7B8E57"),
    ("3.3% 减仓区", 0.033, "#D98B39"),
    ("3.1% 高估区", 0.031, "#C23B3B"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price", type=Path, default=DEFAULT_PRICE)
    parser.add_argument("--pit", type=Path, default=DEFAULT_PIT)
    parser.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_for_manifest(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def load_prices(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            session_date = date.fromisoformat(row["session_date"])
            if not (START_DATE <= session_date <= END_DATE):
                continue
            close_raw = row.get("close", "")
            close = float(close_raw) if close_raw not in {"", None} else math.nan
            rows.append(
                {
                    "date": session_date,
                    "close": close,
                    "trade_status": row.get("trade_status", ""),
                }
            )
    if not rows:
        raise RuntimeError(f"No prices in frozen chart window: {path}")
    return rows


def load_trades(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            fill_date = date.fromisoformat(row["session_date"])
            if not (START_DATE <= fill_date <= END_DATE):
                continue
            if row["status"] != "FILLED":
                continue
            rows.append(
                {
                    "order_id": row["order_id"],
                    "signal_date": date.fromisoformat(row["signal_date"]),
                    "date": fill_date,
                    "side": row["side"],
                    "price": float(row["fill_price_cny"]),
                    "quantity": int(row["filled_quantity"]),
                }
            )
    rows.sort(key=lambda item: (item["date"], item["order_id"]))
    return rows


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float, float, float],
    *,
    fill: str,
    width: int = 1,
    dash: int = 8,
    gap: int = 6,
) -> None:
    x1, y1, x2, y2 = xy
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    ux = (x2 - x1) / length
    uy = (y2 - y1) / length
    cursor = 0.0
    while cursor < length:
        segment_end = min(cursor + dash, length)
        draw.line(
            (
                x1 + ux * cursor,
                y1 + uy * cursor,
                x1 + ux * segment_end,
                y1 + uy * segment_end,
            ),
            fill=fill,
            width=width,
        )
        cursor += dash + gap


def draw_step_series(
    draw: ImageDraw.ImageDraw,
    points: Iterable[tuple[float, float]],
    *,
    fill: str,
    width: int,
) -> None:
    iterator = iter(points)
    try:
        previous = next(iterator)
    except StopIteration:
        return
    for current in iterator:
        draw.line(
            (previous[0], previous[1], current[0], previous[1]),
            fill=fill,
            width=width,
        )
        draw.line(
            (current[0], previous[1], current[0], current[1]),
            fill=fill,
            width=width,
        )
        previous = current


def centered_text(
    draw: ImageDraw.ImageDraw,
    center_x: float,
    y: float,
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    draw.text((center_x - width / 2, y), text, font=font, fill=fill)


def render_chart(
    prices: list[dict[str, object]],
    trades: list[dict[str, object]],
    pit_path: Path,
    output: Path,
) -> dict[str, object]:
    selector = PITDividendSelector.from_csv(pit_path)
    for row in prices:
        record, _ = selector.select(shanghai_close(row["date"]))
        row["dps"] = float(record.dps) if record is not None else math.nan
        row["pit_record_id"] = record.record_id if record is not None else None

    canvas_width, canvas_height = 2000, 1220
    image = Image.new("RGB", (canvas_width, canvas_height), "#F8FAFC")
    draw = ImageDraw.Draw(image)

    title_font = load_font(38, bold=True)
    subtitle_font = load_font(21)
    axis_font = load_font(18)
    small_font = load_font(16)
    tiny_font = load_font(14)
    note_font = load_font(17)

    left, right = 135, 1920
    top_y1, top_y2 = 190, 785
    bottom_y1, bottom_y2 = 895, 1080

    draw.text(
        (left, 35),
        "HD-ANCHOR-001｜P00交易—时间图与股息锚价格分档",
        font=title_font,
        fill="#172033",
    )
    draw.text(
        (left, 88),
        "600900.SH · 回顾性L2 · 2022-03-10—2025-09-09 · 未复权收盘价 · 标记为T+1收盘实际成交",
        font=subtitle_font,
        fill="#536174",
    )

    x_start, x_end = START_DATE.toordinal(), END_DATE.toordinal()

    def x_coord(value: date) -> float:
        return left + (value.toordinal() - x_start) / (x_end - x_start) * (right - left)

    anchor_values: list[float] = []
    close_values: list[float] = []
    for row in prices:
        close = float(row["close"])
        if math.isfinite(close):
            close_values.append(close)
        dps = float(row["dps"])
        if math.isfinite(dps):
            anchor_values.extend(dps / threshold for _, threshold, _ in BANDS)

    y_values = close_values + anchor_values
    y_min = math.floor((min(y_values) - 0.5) / 2) * 2
    y_max = math.ceil((max(y_values) + 0.5) / 2) * 2

    def y_coord(value: float) -> float:
        return top_y2 - (value - y_min) / (y_max - y_min) * (top_y2 - top_y1)

    draw.rounded_rectangle(
        (left, top_y1, right, top_y2),
        radius=8,
        fill="#FFFFFF",
        outline="#D8DEE9",
        width=2,
    )
    draw.rounded_rectangle(
        (left, bottom_y1, right, bottom_y2),
        radius=8,
        fill="#FFFFFF",
        outline="#D8DEE9",
        width=2,
    )

    tick = math.ceil(y_min / 2) * 2
    while tick <= y_max:
        y = y_coord(tick)
        draw_dashed_line(draw, (left, y, right, y), fill="#E6EAF0", width=1)
        label = f"{tick:.0f}"
        box = draw.textbbox((0, 0), label, font=axis_font)
        draw.text(
            (left - 14 - (box[2] - box[0]), y - 11),
            label,
            font=axis_font,
            fill="#596579",
        )
        tick += 2

    for year in range(START_DATE.year, END_DATE.year + 1):
        for month in (1, 7):
            marker_date = date(year, month, 1)
            if not (START_DATE <= marker_date <= END_DATE):
                continue
            x = x_coord(marker_date)
            draw_dashed_line(draw, (x, top_y1, x, top_y2), fill="#EEF1F5", width=1)
            draw_dashed_line(draw, (x, bottom_y1, x, bottom_y2), fill="#EEF1F5", width=1)
            label = f"{year}" if month == 1 else "7月"
            centered_text(
                draw,
                x,
                bottom_y2 + 10,
                label,
                font=small_font,
                fill="#68758A",
            )

    draw.text((40, top_y1 - 4), "价格\n(元/股)", font=axis_font, fill="#465267")
    draw.text((48, bottom_y1 - 4), "持仓\n(股)", font=axis_font, fill="#465267")

    legend_x = left
    legend_y = 137
    draw.line((legend_x, legend_y + 9, legend_x + 38, legend_y + 9), fill="#111827", width=4)
    draw.text((legend_x + 48, legend_y - 4), "未复权收盘价", font=small_font, fill="#2C3648")
    legend_x += 190
    for label, _, color in BANDS:
        draw.line((legend_x, legend_y + 9, legend_x + 34, legend_y + 9), fill=color, width=3)
        draw.text((legend_x + 42, legend_y - 4), label, font=small_font, fill="#2C3648")
        legend_x += 205
    draw.polygon(
        [(legend_x + 8, legend_y + 17), (legend_x + 17, legend_y), (legend_x + 26, legend_y + 17)],
        fill="#159947",
    )
    draw.text((legend_x + 33, legend_y - 4), "买入", font=small_font, fill="#2C3648")
    legend_x += 92
    draw.polygon(
        [(legend_x + 8, legend_y), (legend_x + 26, legend_y), (legend_x + 17, legend_y + 17)],
        fill="#D63636",
    )
    draw.text((legend_x + 33, legend_y - 4), "卖出", font=small_font, fill="#2C3648")

    for _, threshold, color in BANDS:
        segments: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        for row in prices:
            dps = float(row["dps"])
            if not math.isfinite(dps):
                if current:
                    segments.append(current)
                    current = []
                continue
            current.append((x_coord(row["date"]), y_coord(dps / threshold)))
        if current:
            segments.append(current)
        for segment in segments:
            draw_step_series(draw, segment, fill=color, width=3)

    price_points = [
        (x_coord(row["date"]), y_coord(float(row["close"])))
        for row in prices
        if math.isfinite(float(row["close"]))
    ]
    if len(price_points) > 1:
        draw.line(price_points, fill="#151A22", width=4, joint="curve")

    shares = INITIAL_SHARES
    trades_by_date: dict[date, list[dict[str, object]]] = {}
    for trade in trades:
        trades_by_date.setdefault(trade["date"], []).append(trade)
        side = str(trade["side"])
        quantity = int(trade["quantity"])
        shares += quantity if side == "BUY" else -quantity
        trade["post_shares"] = shares

    for index, trade in enumerate(trades):
        x = x_coord(trade["date"])
        y = y_coord(float(trade["price"]))
        side = str(trade["side"])
        if side == "BUY":
            polygon = [(x - 10, y + 10), (x, y - 11), (x + 10, y + 10)]
            color = "#159947"
            label_y = y + 14 + (index % 2) * 18
        else:
            polygon = [(x - 10, y - 10), (x + 10, y - 10), (x, y + 11)]
            color = "#D63636"
            label_y = y - 35 - (index % 2) * 18
        draw.polygon(polygon, fill=color, outline="#FFFFFF")
        centered_text(
            draw,
            x,
            label_y,
            f"{side[0]}{int(trade['post_shares'])}",
            font=tiny_font,
            fill=color,
        )

    holding_min, holding_max = 900, 1500

    def holding_y(value: int) -> float:
        return bottom_y2 - (value - holding_min) / (holding_max - holding_min) * (
            bottom_y2 - bottom_y1
        )

    for level in range(1000, 1501, 100):
        y = holding_y(level)
        color = "#D2D8E2" if level in {1000, 1500} else "#E8EBF0"
        draw_dashed_line(draw, (left, y, right, y), fill=color, width=1)
        label = str(level)
        box = draw.textbbox((0, 0), label, font=small_font)
        draw.text(
            (left - 14 - (box[2] - box[0]), y - 9),
            label,
            font=small_font,
            fill="#596579",
        )

    holding_points: list[tuple[float, float]] = []
    current_shares = INITIAL_SHARES
    for row in prices:
        for trade in trades_by_date.get(row["date"], []):
            quantity = int(trade["quantity"])
            current_shares += quantity if trade["side"] == "BUY" else -quantity
        holding_points.append((x_coord(row["date"]), holding_y(current_shares)))
    draw_step_series(draw, holding_points, fill="#6B4FC6", width=5)

    for trade in trades:
        x = x_coord(trade["date"])
        y = holding_y(int(trade["post_shares"]))
        color = "#159947" if trade["side"] == "BUY" else "#D63636"
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=color, outline="#FFFFFF", width=2)
        draw.text(
            (x + 8, y - 27),
            str(int(trade["post_shares"])),
            font=tiny_font,
            fill=color,
        )

    draw.text(
        (left + 12, bottom_y1 + 12),
        "紫线：P00日终持仓；灰虚线：1000股核心仓 / 1500股上限",
        font=small_font,
        fill="#5B6578",
    )

    valid_anchor_sessions = sum(math.isfinite(float(row["dps"])) for row in prices)
    buy_count = sum(trade["side"] == "BUY" for trade in trades)
    sell_count = sum(trade["side"] == "SELL" for trade in trades)
    final_shares = int(trades[-1]["post_shares"]) if trades else INITIAL_SHARES

    note = (
        "注：价格分档线 = 决策时点有效PIT年度DPS ÷ 股息率阈值；它表示原始股息率区间，"
        "不等同于滞回状态机的最终买卖边界或可执行目标。"
    )
    draw.text((left, 1135), note, font=note_font, fill="#4D596D")
    draw.text(
        (left, 1168),
        f"只读派生：{len(prices)}个会话，{valid_anchor_sessions}个会话存在有效PIT锚；"
        f"实际成交{len(trades)}笔（买{buy_count}、卖{sell_count}），期末{final_shares}股。",
        font=note_font,
        fill="#4D596D",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    return {
        "sessions": len(prices),
        "valid_anchor_sessions": valid_anchor_sessions,
        "trades": len(trades),
        "buys": buy_count,
        "sells": sell_count,
        "final_shares": final_shares,
    }


def write_manifest(
    *,
    output: Path,
    inputs: list[Path],
    statistics: dict[str, object],
) -> Path:
    manifest_path = output.with_name(output.stem + "_manifest.json")
    payload = {
        "statement_type": "已观察事实",
        "artifact_version": "P00-TRADE-TIMELINE-DIVIDEND-ANCHOR-BANDS-1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "READONLY_VISUALIZATION_FROM_FROZEN_INPUTS_NO_STRATEGY_RERUN_NO_PERFORMANCE_RECALCULATION",
        "window": "[2022-03-10,2025-09-10)",
        "inputs": [
            {
                "path": path_for_manifest(path),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in inputs
        ],
        "script": {
            "path": path_for_manifest(Path(__file__)),
            "sha256": sha256(Path(__file__).resolve()),
        },
        "output": {
            "path": path_for_manifest(output),
            "sha256": sha256(output),
            "size_bytes": output.stat().st_size,
        },
        "statistics": statistics,
        "interpretation_guard": (
            "Raw dividend-yield price bands are not identical to hysteresis-state "
            "buy/sell boundaries, ideal inventory, adjacent state, or executable target."
        ),
        "evidence_ceiling": "L2_RETROSPECTIVE_UNCHANGED",
        "dry_run": True,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    args = parse_args()
    price_path = args.price.resolve()
    pit_path = args.pit.resolve()
    trades_path = args.trades.resolve()
    output = args.output.resolve()

    prices = load_prices(price_path)
    trades = load_trades(trades_path)
    statistics = render_chart(prices, trades, pit_path, output)
    manifest = write_manifest(
        output=output,
        inputs=[price_path, pit_path, trades_path],
        statistics=statistics,
    )
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "manifest": manifest.as_posix(),
                **statistics,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
