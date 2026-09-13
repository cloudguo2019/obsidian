"""Auditable Stage 8 account and execution engine for HD-ANCHOR-001.

This module implements protocol versions 1.1--1.5.  It deliberately contains no
return, CAGR, drawdown, Sharpe, or OOS reporting code.  Formal economic runs and
the pre-OOS exposure calibration remain separately authorized actions.
"""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Iterable, Mapping, Sequence


getcontext().prec = 28

ZERO = Decimal("0")
CENT = Decimal("0.01")
ACCOUNT_QUANTUM = Decimal("0.0001")
SHANGHAI_TZ = timezone(timedelta(hours=8))


class Stage8Error(RuntimeError):
    """Base class for fail-closed Stage 8 errors."""


class DataGateError(Stage8Error):
    """Raised when an input required by the frozen protocol is unavailable."""


class ReconciliationError(Stage8Error):
    """Raised when a daily account cannot reconcile within CNY 0.01."""


def dec(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def account_amount(value: object) -> Decimal:
    return dec(value).quantize(ACCOUNT_QUANTUM, rounding=ROUND_HALF_UP)


def fee_amount(value: object) -> Decimal:
    return dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def required_date(value: str | date | None, field_name: str) -> date:
    result = parse_date(value)
    if result is None:
        raise DataGateError(f"required date is missing: {field_name}")
    return result


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value.replace(" ", "T"))
    if result.tzinfo is None:
        raise DataGateError(f"timezone is required: {value!r}")
    return result


def shanghai_close(session_date: date) -> datetime:
    return datetime.combine(session_date, time(15, 0), tzinfo=SHANGHAI_TZ)


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_calendar_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


@dataclass(frozen=True)
class FeeRule:
    fee_type: str
    effective_start: date | None
    effective_end: date | None
    charge_side: str
    rate_basis: str
    rate: Decimal
    minimum_cny_per_parent_order: Decimal | None = None

    def applies(self, session_date: date, side: str) -> bool:
        in_range = (
            (self.effective_start is None or self.effective_start <= session_date)
            and (self.effective_end is None or session_date <= self.effective_end)
        )
        side_ok = self.charge_side == "BOTH" or self.charge_side == side
        return in_range and side_ok


@dataclass(frozen=True)
class FeeBreakdown:
    components: Mapping[str, Decimal]

    @property
    def total(self) -> Decimal:
        return account_amount(sum(self.components.values(), ZERO))


class TransactionCostSchedule:
    """Date-effective A-share fee schedule with per-parent-order commission."""

    def __init__(self, rules: Iterable[FeeRule], nominal_value_per_share: object = "1"):
        self.rules = tuple(rules)
        self.nominal_value_per_share = dec(nominal_value_per_share)
        if not self.rules:
            raise DataGateError("transaction fee schedule is empty")

    @classmethod
    def from_csv(cls, path: str | Path, nominal_value_per_share: object = "1") -> "TransactionCostSchedule":
        rules: list[FeeRule] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["market"] != "SSE_A_SHARE":
                    continue
                if not row["rate_decimal"]:
                    continue
                rules.append(
                    FeeRule(
                        fee_type=row["fee_type"],
                        effective_start=parse_date(row["effective_start"]),
                        effective_end=parse_date(row["effective_end"]),
                        charge_side=row["charge_side"],
                        rate_basis=row["rate_basis"],
                        rate=dec(row["rate_decimal"]),
                        minimum_cny_per_parent_order=(
                            dec(row["minimum_cny_per_parent_order"])
                            if row["minimum_cny_per_parent_order"]
                            else None
                        ),
                    )
                )
        return cls(rules, nominal_value_per_share)

    def calculate(self, session_date: date, side: str, quantity: int, price: Decimal) -> FeeBreakdown:
        if side not in {"BUY", "SELL"}:
            raise ValueError(f"invalid side: {side}")
        if quantity <= 0 or price <= ZERO:
            raise ValueError("quantity and price must be positive")
        components: dict[str, Decimal] = {}
        for fee_type in sorted({rule.fee_type for rule in self.rules}):
            dated_candidates = [
                rule for rule in self.rules
                if rule.fee_type == fee_type
                and (rule.effective_start is None or rule.effective_start <= session_date)
                and (rule.effective_end is None or session_date <= rule.effective_end)
            ]
            if len(dated_candidates) > 1:
                raise DataGateError(f"overlapping {fee_type} rules on {session_date}")
            if not dated_candidates:
                raise DataGateError(f"missing {fee_type} rule on {session_date}")
            rule = dated_candidates[0]
            if rule.charge_side not in {"BOTH", side}:
                continue
            if rule.rate_basis == "transaction_amount":
                basis = dec(quantity) * price
            elif rule.rate_basis == "nominal_value":
                basis = dec(quantity) * self.nominal_value_per_share
            else:
                raise DataGateError(f"unsupported fee basis: {rule.rate_basis}")
            charge = fee_amount(basis * rule.rate)
            if rule.minimum_cny_per_parent_order is not None:
                charge = max(charge, fee_amount(rule.minimum_cny_per_parent_order))
            components[fee_type] = charge
        if "BROKER_COMMISSION" not in components:
            raise DataGateError(f"broker commission rule missing on {session_date}")
        return FeeBreakdown(components)


@dataclass(frozen=True)
class DividendTaxRule:
    version: str
    effective_start: date | None
    effective_end: date | None
    holding_period_condition: str
    tax_rate: Decimal
    collection_timing: str
    initial_withholding_rate: Decimal | None = None


class DividendTaxSchedule:
    """Frozen PRC resident-individual dividend tax schedule."""

    def __init__(self, rules: Iterable[DividendTaxRule]):
        self.rules = tuple(rules)
        if not self.rules:
            raise DataGateError("dividend tax schedule is empty")

    @classmethod
    def from_csv(cls, path: str | Path) -> "DividendTaxSchedule":
        rules: list[DividendTaxRule] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if not row["tax_rate_decimal"]:
                    continue
                rules.append(
                    DividendTaxRule(
                        version=row["tax_rule_version"],
                        effective_start=parse_date(row["effective_start"]),
                        effective_end=parse_date(row["effective_end"]),
                        holding_period_condition=row["holding_period_condition"],
                        tax_rate=dec(row["tax_rate_decimal"]),
                        collection_timing=row["collection_timing"],
                        initial_withholding_rate=(
                            dec(row["initial_withholding_rate_decimal"])
                            if row["initial_withholding_rate_decimal"]
                            else None
                        ),
                    )
                )
        return cls(rules)

    @staticmethod
    def holding_condition(acquired: date, as_of: date) -> str:
        if as_of < acquired:
            raise DataGateError("holding-period date precedes acquisition")
        if as_of <= add_calendar_months(acquired, 1):
            return "LE_1_CALENDAR_MONTH"
        if as_of <= add_calendar_years(acquired, 1):
            return "GT_1_CALENDAR_MONTH_LE_1_YEAR"
        return "GT_1_YEAR"

    def select(self, version: str, acquired: date, as_of: date) -> DividendTaxRule:
        # The corporate-action row has already frozen the policy version that
        # governs the entitlement.  A later sale can occur after that version's
        # effective_end, so filtering the version again by sale date would drop
        # a valid historical liability.
        version_rules = [rule for rule in self.rules if rule.version == version]
        if not version_rules:
            raise DataGateError(f"no dividend tax rule version {version!r}")
        if any(rule.holding_period_condition == "ALL_HOLDING_PERIODS" for rule in version_rules):
            matches = [
                rule for rule in version_rules
                if rule.holding_period_condition == "ALL_HOLDING_PERIODS"
            ]
        else:
            condition = self.holding_condition(acquired, as_of)
            matches = [rule for rule in version_rules if rule.holding_period_condition == condition]
        if len(matches) != 1:
            raise DataGateError(f"ambiguous dividend tax rule {version!r} on {as_of}")
        return matches[0]

    def initial_withholding_rate(self, rule: DividendTaxRule) -> Decimal:
        if rule.collection_timing == "AT_PAYMENT":
            return rule.tax_rate
        if rule.collection_timing == "FINAL_BY_HOLDING_PERIOD":
            if rule.initial_withholding_rate is None:
                raise DataGateError("initial withholding rate is missing")
            return rule.initial_withholding_rate
        if rule.collection_timing in {"SUPPLEMENT_AT_SALE", "NO_TAX_OVER_ONE_YEAR"}:
            return ZERO
        raise DataGateError(f"unsupported collection timing: {rule.collection_timing}")


@dataclass
class Lot:
    lot_id: str
    acquired_date: date
    shares: int
    price: Decimal
    available_session_index: int


@dataclass
class RecordDateLot:
    lot_id: str
    acquired_date: date
    shares: int


@dataclass
class DividendClaim:
    claim_id: str
    action_id: str
    lot_id: str
    acquired_date: date
    entitled_shares: int
    remaining_unsold_shares: int
    gross_per_share: Decimal
    tax_rule_version: str
    pay_date: date
    paid: bool = False
    withholding_rate_paid: Decimal = ZERO

    @property
    def gross_amount(self) -> Decimal:
        return account_amount(dec(self.entitled_shares) * self.gross_per_share)


@dataclass(frozen=True)
class CorporateAction:
    action_id: str
    record_date: date
    ex_date: date
    pay_date: date
    cash_dividend_per_share: Decimal
    tax_rule_version: str
    share_transfer_per_share: Decimal = ZERO
    action_type: str = "CASH_DIVIDEND"
    record_status: str = "VALID"


@dataclass(frozen=True)
class PITDividendRecord:
    record_id: str
    available_time: datetime
    effective_time: datetime
    expiry_time: datetime
    superseded_time: datetime | None
    dps: Decimal
    method: str = "SHAREHOLDER_MEETING_CONFIRMED_ANNUAL_DPS_V1"


class PITDividendSelector:
    METHOD = "SHAREHOLDER_MEETING_CONFIRMED_ANNUAL_DPS_V1"

    def __init__(self, records: Iterable[PITDividendRecord]):
        self.records = tuple(records)

    @classmethod
    def from_csv(cls, path: str | Path) -> "PITDividendSelector":
        records: list[PITDividendRecord] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                records.append(
                    PITDividendRecord(
                        record_id=row["record_id"],
                        available_time=parse_datetime(row["available_time"]),
                        effective_time=parse_datetime(row["effective_time"]),
                        expiry_time=parse_datetime(row["expiry_time"]),
                        superseded_time=(
                            parse_datetime(row["superseded_time"])
                            if row["superseded_time"] else None
                        ),
                        dps=dec(row["expected_annual_dividend_per_share"]),
                        method=row["estimate_method"],
                    )
                )
        return cls(records)

    def select(self, decision_time: datetime) -> tuple[PITDividendRecord | None, str | None]:
        candidates = [
            record for record in self.records
            if record.method == self.METHOD
            and record.available_time <= decision_time
            and record.effective_time <= decision_time
            and decision_time <= record.expiry_time
            and (record.superseded_time is None or decision_time < record.superseded_time)
        ]
        if not candidates:
            return None, "NO_VALID_PIT_DIVIDEND"
        selected = max(candidates, key=lambda item: (item.available_time, item.record_id))
        if selected.dps <= ZERO:
            return None, "ZERO_DIVIDEND_BLOCK"
        return selected, None


@dataclass(frozen=True)
class Session:
    session_date: date
    close: Decimal | None
    trade_status: str = "TRADING"
    limit_up: Decimal | None = None
    limit_down: Decimal | None = None


@dataclass(frozen=True)
class OrderInstruction:
    order_id: str
    signal_date: date
    execute_session_index: int
    original_shares: int
    target_shares: int
    reason: str


@dataclass(frozen=True)
class FillResult:
    order_id: str
    status: str
    reason: str
    session_date: date
    side: str | None
    quantity: int
    price: Decimal | None
    fees: FeeBreakdown
    deferred_tax_paid: Decimal
    pre_shares: int
    post_shares: int


@dataclass(frozen=True)
class StrategyDecision:
    target_shares: int
    reason: str


@dataclass(frozen=True)
class DailySnapshot:
    session_date: date
    mark: Decimal
    cash: Decimal
    shares: int
    available_shares: int
    dividend_receivable: Decimal
    tax_liability: Decimal
    nav: Decimal
    price_pnl: Decimal
    new_dividend_entitlement: Decimal
    tax_reserve_change: Decimal
    transaction_fees: Decimal
    expected_nav_change: Decimal
    actual_nav_change: Decimal
    reconciliation_difference: Decimal
    signal_blocker: str | None
    generated_order: OrderInstruction | None
    fills: tuple[FillResult, ...]


class Account:
    """FIFO lot account with T+1 inventory and dividend tax reserves."""

    def __init__(
        self,
        cash: object,
        initial_shares: int,
        initial_price: object,
        initial_acquired_date: date,
        initial_session_index: int,
        fee_schedule: TransactionCostSchedule,
        tax_schedule: DividendTaxSchedule,
    ):
        self.cash = account_amount(cash)
        self.fee_schedule = fee_schedule
        self.tax_schedule = tax_schedule
        self.lots: list[Lot] = []
        if initial_shares:
            self.lots.append(
                Lot(
                    lot_id="INITIAL",
                    acquired_date=initial_acquired_date,
                    shares=initial_shares,
                    price=dec(initial_price),
                    available_session_index=initial_session_index,
                )
            )
        self.record_snapshots: dict[str, list[RecordDateLot]] = {}
        self.claims: list[DividendClaim] = []
        self._tax_liability = ZERO
        self._lot_counter = 0

    @property
    def shares(self) -> int:
        return sum(lot.shares for lot in self.lots)

    def available_shares(self, session_index: int) -> int:
        return sum(lot.shares for lot in self.lots if lot.available_session_index <= session_index)

    @property
    def average_price(self) -> Decimal:
        if not self.shares:
            return ZERO
        total = sum(dec(lot.shares) * lot.price for lot in self.lots)
        return total / dec(self.shares)

    @property
    def dividend_receivable(self) -> Decimal:
        return account_amount(sum((claim.gross_amount for claim in self.claims if not claim.paid), ZERO))

    @property
    def tax_liability(self) -> Decimal:
        return account_amount(self._tax_liability)

    def nav(self, mark: Decimal) -> Decimal:
        return account_amount(
            self.cash + dec(self.shares) * mark + self.dividend_receivable - self.tax_liability
        )

    def snapshot_record_date(self, action: CorporateAction) -> None:
        self.record_snapshots[action.action_id] = [
            RecordDateLot(lot.lot_id, lot.acquired_date, lot.shares)
            for lot in self.lots if lot.shares > 0
        ]

    def recognize_dividend(self, action: CorporateAction) -> Decimal:
        if action.record_status != "VALID" or action.action_type != "CASH_DIVIDEND":
            return ZERO
        if action.share_transfer_per_share != ZERO:
            raise DataGateError(
                f"share transfer is outside the Stage 8 cash-only implementation: {action.action_id}"
            )
        if any(claim.action_id == action.action_id for claim in self.claims):
            raise DataGateError(f"duplicate dividend recognition: {action.action_id}")
        gross = ZERO
        for item in self.record_snapshots.get(action.action_id, []):
            claim = DividendClaim(
                claim_id=f"{action.action_id}:{item.lot_id}",
                action_id=action.action_id,
                lot_id=item.lot_id,
                acquired_date=item.acquired_date,
                entitled_shares=item.shares,
                remaining_unsold_shares=item.shares,
                gross_per_share=action.cash_dividend_per_share,
                tax_rule_version=action.tax_rule_version,
                pay_date=action.pay_date,
            )
            self.claims.append(claim)
            gross += claim.gross_amount
        return account_amount(gross)

    def _claim_reserve(self, claim: DividendClaim, as_of: date) -> Decimal:
        if claim.remaining_unsold_shares <= 0:
            return ZERO
        rule = self.tax_schedule.select(claim.tax_rule_version, claim.acquired_date, as_of)
        gross_open = dec(claim.remaining_unsold_shares) * claim.gross_per_share
        final_tax = fee_amount(gross_open * rule.tax_rate)
        withholding_credit = fee_amount(gross_open * claim.withholding_rate_paid)
        return max(final_tax - withholding_credit, ZERO)

    def revalue_tax_liability(self, as_of: date) -> Decimal:
        previous = self.tax_liability
        current = sum((self._claim_reserve(claim, as_of) for claim in self.claims), ZERO)
        self._tax_liability = account_amount(current)
        return account_amount(self.tax_liability - previous)

    def pay_dividend(self, action: CorporateAction, as_of: date) -> tuple[Decimal, Decimal]:
        matching = [claim for claim in self.claims if claim.action_id == action.action_id and not claim.paid]
        if not matching:
            return ZERO, ZERO
        before = self.tax_liability
        gross = sum((claim.gross_amount for claim in matching), ZERO)
        for claim in matching:
            rule = self.tax_schedule.select(claim.tax_rule_version, claim.acquired_date, as_of)
            claim.withholding_rate_paid = self.tax_schedule.initial_withholding_rate(rule)
            claim.paid = True
        current = sum((self._claim_reserve(claim, as_of) for claim in self.claims), ZERO)
        self._tax_liability = account_amount(current)
        liability_released = account_amount(before - self.tax_liability)
        if liability_released < ZERO:
            raise ReconciliationError("payment increased rather than settled tax liability")
        self.cash = account_amount(self.cash + gross - liability_released)
        return account_amount(gross), liability_released

    def _settle_claims_for_sale(self, lot_id: str, quantity: int, as_of: date) -> Decimal:
        matching = [
            claim for claim in self.claims
            if claim.lot_id == lot_id and claim.remaining_unsold_shares > 0
        ]
        if not matching:
            return ZERO
        before = sum((self._claim_reserve(claim, as_of) for claim in matching), ZERO)
        for claim in matching:
            if claim.remaining_unsold_shares < quantity:
                raise ReconciliationError("claim shares are below linked lot sale quantity")
            claim.remaining_unsold_shares -= quantity
        after = sum((self._claim_reserve(claim, as_of) for claim in matching), ZERO)
        return account_amount(before - after)

    def execute(
        self,
        order: OrderInstruction,
        session: Session,
        session_index: int,
    ) -> FillResult:
        empty_fees = FeeBreakdown({})
        pre_shares = self.shares
        delta = order.target_shares - pre_shares
        if delta == 0:
            return FillResult(order.order_id, "NOOP", "TARGET_ALREADY_REACHED", session.session_date,
                              None, 0, session.close, empty_fees, ZERO, pre_shares, pre_shares)
        side = "BUY" if delta > 0 else "SELL"
        quantity = abs(delta)
        if session.trade_status != "TRADING":
            return FillResult(order.order_id, "UNFILLED", "NOT_TRADABLE", session.session_date,
                              side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
        if session.close is None or session.close <= ZERO:
            return FillResult(order.order_id, "UNFILLED", "INVALID_FINAL_CLOSE", session.session_date,
                              side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
        # Direct account callers receive the same as-of-date reserve treatment
        # as the daily engine.  In the engine this is a zero-change idempotent
        # call because the reserve was already remeasured before the fill.
        self.revalue_tax_liability(session.session_date)
        if side == "BUY":
            if session.limit_up is None:
                return FillResult(order.order_id, "UNFILLED", "MISSING_BUY_PROTECTION_LIMIT", session.session_date,
                                  side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
            if session.close > session.limit_up:
                return FillResult(order.order_id, "UNFILLED", "CLOSE_ABOVE_BUY_LIMIT", session.session_date,
                                  side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
        else:
            if session.limit_down is None:
                return FillResult(order.order_id, "UNFILLED", "MISSING_SELL_PROTECTION_LIMIT", session.session_date,
                                  side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
            if session.close < session.limit_down:
                return FillResult(order.order_id, "UNFILLED", "CLOSE_BELOW_SELL_LIMIT", session.session_date,
                                  side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)

        fees = self.fee_schedule.calculate(session.session_date, side, quantity, session.close)
        notional = account_amount(dec(quantity) * session.close)
        if side == "BUY":
            required = account_amount(notional + fees.total)
            if self.cash < required:
                return FillResult(order.order_id, "UNFILLED", "INSUFFICIENT_CASH", session.session_date,
                                  side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
            self.cash = account_amount(self.cash - required)
            self._lot_counter += 1
            self.lots.append(
                Lot(
                    lot_id=f"LOT-{self._lot_counter:06d}",
                    acquired_date=session.session_date,
                    shares=quantity,
                    price=session.close,
                    available_session_index=session_index + 1,
                )
            )
            deferred_tax = ZERO
        else:
            if self.available_shares(session_index) < quantity:
                return FillResult(order.order_id, "UNFILLED", "INSUFFICIENT_T1_INVENTORY", session.session_date,
                                  side, quantity, session.close, empty_fees, ZERO, pre_shares, pre_shares)
            remaining = quantity
            deferred_tax = ZERO
            for lot in list(self.lots):
                if lot.available_session_index > session_index or remaining == 0:
                    continue
                sold = min(lot.shares, remaining)
                deferred_tax += self._settle_claims_for_sale(lot.lot_id, sold, session.session_date)
                lot.shares -= sold
                remaining -= sold
                if lot.shares == 0:
                    self.lots.remove(lot)
            if remaining:
                raise ReconciliationError("FIFO sale did not consume the requested quantity")
            self._tax_liability = account_amount(
                sum((self._claim_reserve(claim, session.session_date) for claim in self.claims), ZERO)
            )
            self.cash = account_amount(self.cash + notional - fees.total - deferred_tax)

        return FillResult(
            order.order_id, "FILLED", "ASSUMED_FULL_AT_FINAL_CLOSE", session.session_date,
            side, quantity, session.close, fees, account_amount(deferred_tax), pre_shares, self.shares
        )


@dataclass(frozen=True)
class StrategyConfig:
    core_shares: int = 1000
    max_total_shares: int = 1500
    max_auto_add_shares: int = 1400
    step_shares: int = 100
    exit_target_shares: int = 0
    loss_stop_add: Decimal = Decimal("-0.10")
    buy_yields: Mapping[int, Decimal] = field(default_factory=lambda: {
        1000: Decimal("0.033"),
        1100: Decimal("0.035"),
        1200: Decimal("0.040"),
        1300: Decimal("0.042"),
    })
    sell_yields: Mapping[int, Decimal] = field(default_factory=lambda: {
        1100: Decimal("0.031"),
        1200: Decimal("0.033"),
        1300: Decimal("0.035"),
        1400: Decimal("0.040"),
        1500: Decimal("0.042"),
    })


class HDAnchorStrategy:
    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()

    @staticmethod
    def _both_at_or_below(previous: Decimal, current: Decimal, boundary: Decimal) -> bool:
        return previous <= boundary and current <= boundary

    @staticmethod
    def _both_at_or_above(previous: Decimal, current: Decimal, boundary: Decimal) -> bool:
        return previous >= boundary and current >= boundary

    def decide(
        self,
        *,
        shares: int,
        average_price: Decimal,
        total_assets: Decimal,
        previous_close: Decimal,
        current_close: Decimal,
        dividend_dps: Decimal,
        fundamental_gate: str = "NORMAL",
    ) -> StrategyDecision:
        cfg = self.config
        if dividend_dps <= ZERO or current_close <= ZERO or previous_close <= ZERO or total_assets <= ZERO:
            return StrategyDecision(shares, "INVALID_REQUIRED_INPUT")
        if fundamental_gate == "REVIEW":
            return StrategyDecision(shares, "REVIEW_HOLD")
        if fundamental_gate == "EXIT":
            target = cfg.exit_target_shares if shares > cfg.exit_target_shares else shares
            return StrategyDecision(target, "FUNDAMENTAL_EXIT")
        if fundamental_gate not in {"NORMAL", "STOP_ADD"}:
            return StrategyDecision(shares, "UNKNOWN_FUNDAMENTAL_GATE")

        if shares > cfg.max_total_shares:
            target = max(shares - cfg.step_shares, cfg.max_total_shares)
            return StrategyDecision(target, "EXCESS_POSITION_CORRECTION")
        valid_states = set(range(0, cfg.max_total_shares + 1, cfg.step_shares))
        if shares not in valid_states:
            return StrategyDecision(shares, "ILLEGAL_DISCRETE_STATE_HOLD")

        target = shares
        reason = "HOLD"
        if shares < cfg.core_shares:
            target = min(shares + cfg.step_shares, cfg.core_shares)
            reason = "CORE_BUILD"
        elif shares in cfg.buy_yields:
            buy_boundary = dividend_dps / cfg.buy_yields[shares]
            if self._both_at_or_below(previous_close, current_close, buy_boundary):
                target = min(shares + cfg.step_shares, cfg.max_auto_add_shares)
                reason = "ADJACENT_BUY"
        if target == shares and shares in cfg.sell_yields:
            sell_boundary = dividend_dps / cfg.sell_yields[shares]
            if self._both_at_or_above(previous_close, current_close, sell_boundary):
                target = max(shares - cfg.step_shares, cfg.core_shares)
                reason = "ADJACENT_SELL"

        if target > shares:
            if fundamental_gate == "STOP_ADD":
                return StrategyDecision(shares, "STOP_ADD_HOLD")
            loss_impact = min((current_close - average_price) * dec(shares), ZERO) / total_assets
            if loss_impact <= cfg.loss_stop_add:
                return StrategyDecision(shares, "ACCOUNT_LOSS_STOP_ADD")
        return StrategyDecision(target, reason)


class DailyCloseLaggedEngine:
    """One-account implementation of DAILY_CLOSE_LAGGED_AUCTION_V1."""

    def __init__(
        self,
        account: Account,
        initial_mark: object,
        initial_date: date,
        pit_selector: PITDividendSelector | None = None,
        strategy: HDAnchorStrategy | None = None,
        corporate_actions: Iterable[CorporateAction] = (),
        reconciliation_tolerance: object = "0.01",
    ):
        self.account = account
        self.last_mark = dec(initial_mark)
        self.previous_nav = account.nav(self.last_mark)
        self.previous_signal_close: Decimal | None = self.last_mark
        self.previous_session_date = initial_date
        self.pit_selector = pit_selector
        self.strategy = strategy
        self.reconciliation_tolerance = dec(reconciliation_tolerance)
        self.pending: dict[int, list[OrderInstruction]] = {}
        self.actions = tuple(
            action for action in corporate_actions
            if action.record_status == "VALID" and action.action_type == "CASH_DIVIDEND"
        )
        self._order_counter = 0

    def _actions_on(self, field_name: str, session_date: date) -> list[CorporateAction]:
        return [action for action in self.actions if getattr(action, field_name) == session_date]

    def step(self, session: Session, session_index: int, fundamental_gate: str = "NORMAL") -> DailySnapshot:
        if session.session_date <= self.previous_session_date:
            raise DataGateError("sessions must be strictly increasing")
        opening_shares = self.account.shares
        mark = session.close if session.trade_status == "TRADING" and session.close is not None else self.last_mark
        if mark <= ZERO:
            raise DataGateError("a valid current or carry-forward mark is required")
        price_pnl = account_amount(dec(opening_shares) * (mark - self.last_mark))

        new_dividend = ZERO
        for action in self._actions_on("ex_date", session.session_date):
            new_dividend += self.account.recognize_dividend(action)
        tax_reserve_change = self.account.revalue_tax_liability(session.session_date)
        for action in self._actions_on("pay_date", session.session_date):
            self.account.pay_dividend(action, session.session_date)

        fills: list[FillResult] = []
        transaction_fees = ZERO
        for order in self.pending.pop(session_index, []):
            fill = self.account.execute(order, session, session_index)
            fills.append(fill)
            transaction_fees += fill.fees.total

        for action in self._actions_on("record_date", session.session_date):
            self.account.snapshot_record_date(action)

        generated_order: OrderInstruction | None = None
        signal_blocker: str | None = None
        if self.strategy is not None:
            if session.trade_status != "TRADING" or session.close is None:
                signal_blocker = "NO_TRADABLE_COMPLETED_CLOSE"
            elif self.previous_signal_close is None:
                signal_blocker = "CONFIRMATION_BAR_MISSING"
            elif self.pit_selector is None:
                signal_blocker = "PIT_SELECTOR_MISSING"
            else:
                pit, signal_blocker = self.pit_selector.select(shanghai_close(session.session_date))
                if pit is not None:
                    decision = self.strategy.decide(
                        shares=self.account.shares,
                        average_price=self.account.average_price,
                        total_assets=self.account.nav(mark),
                        previous_close=self.previous_signal_close,
                        current_close=session.close,
                        dividend_dps=pit.dps,
                        fundamental_gate=fundamental_gate,
                    )
                    if decision.target_shares != self.account.shares:
                        self._order_counter += 1
                        generated_order = OrderInstruction(
                            order_id=f"ORDER-{self._order_counter:06d}",
                            signal_date=session.session_date,
                            execute_session_index=session_index + 1,
                            original_shares=self.account.shares,
                            target_shares=decision.target_shares,
                            reason=decision.reason,
                        )
                        self.pending.setdefault(session_index + 1, []).append(generated_order)
                    else:
                        signal_blocker = decision.reason

        nav = self.account.nav(mark)
        actual_change = account_amount(nav - self.previous_nav)
        expected_change = account_amount(price_pnl + new_dividend - tax_reserve_change - transaction_fees)
        difference = account_amount(actual_change - expected_change)
        if abs(difference) > self.reconciliation_tolerance:
            raise ReconciliationError(
                f"{session.session_date}: reconciliation difference {difference} exceeds "
                f"{self.reconciliation_tolerance}"
            )

        snapshot = DailySnapshot(
            session_date=session.session_date,
            mark=mark,
            cash=self.account.cash,
            shares=self.account.shares,
            available_shares=self.account.available_shares(session_index),
            dividend_receivable=self.account.dividend_receivable,
            tax_liability=self.account.tax_liability,
            nav=nav,
            price_pnl=price_pnl,
            new_dividend_entitlement=account_amount(new_dividend),
            tax_reserve_change=tax_reserve_change,
            transaction_fees=account_amount(transaction_fees),
            expected_nav_change=expected_change,
            actual_nav_change=actual_change,
            reconciliation_difference=difference,
            signal_blocker=signal_blocker,
            generated_order=generated_order,
            fills=tuple(fills),
        )
        self.previous_nav = nav
        self.last_mark = mark
        self.previous_session_date = session.session_date
        self.previous_signal_close = (
            session.close if session.trade_status == "TRADING" and session.close is not None else None
        )
        return snapshot


def initialize_research_account(
    *,
    common_assets: object,
    shares: int,
    price_ref: object,
    t0: date,
    initial_session_index: int,
    fee_schedule: TransactionCostSchedule,
    tax_schedule: DividendTaxSchedule,
) -> Account:
    """Create a frozen t0 account without a fictitious initialization order."""

    price = dec(price_ref)
    cash = account_amount(dec(common_assets) - dec(shares) * price)
    if cash < ZERO:
        raise DataGateError("initial inventory would create negative cash")
    acquired = add_calendar_years(t0, -2)
    return Account(
        cash=cash,
        initial_shares=shares,
        initial_price=price,
        initial_acquired_date=acquired,
        initial_session_index=initial_session_index,
        fee_schedule=fee_schedule,
        tax_schedule=tax_schedule,
    )


def load_corporate_actions(path: str | Path) -> tuple[CorporateAction, ...]:
    rows: list[dict[str, str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["record_status"] != "VALID" or row["action_type"] != "CASH_DIVIDEND":
                continue
            rows.append(dict(row))

    # Differential distributions contain one row per eligible share class.
    # This research account represents ordinary secondary-market shares, so a
    # group must resolve to its ORDINARY/PARTICIPATING row and must never sum
    # mutually exclusive class-level DPS values.
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["action_group_id"], []).append(row)

    selected_rows: list[dict[str, str]] = []
    for group_id, group in grouped.items():
        preferred = [
            row for row in group
            if row["action_id"].endswith("-ORDINARY")
            or row["action_id"].endswith("-PARTICIPATING")
        ]
        if len(preferred) == 1:
            selected_rows.append(preferred[0])
            continue
        eligible = [
            row for row in group
            if dec(row["cash_dividend_per_share"]) > ZERO
            and not row["tax_rule_version"].startswith("NOT_APPLICABLE")
        ]
        if len(eligible) != 1:
            raise DataGateError(f"ordinary-share entitlement is ambiguous for {group_id}")
        selected_rows.append(eligible[0])

    actions: list[CorporateAction] = []
    for row in selected_rows:
        actions.append(
                CorporateAction(
                    action_id=row["action_id"],
                    record_date=required_date(row["record_date"], "record_date"),
                    ex_date=required_date(row["ex_date"], "ex_date"),
                    pay_date=required_date(row["pay_date"], "pay_date"),
                    cash_dividend_per_share=dec(row["cash_dividend_per_share"]),
                    tax_rule_version=row["tax_rule_version"],
                    share_transfer_per_share=(
                        dec(row["share_transfer_per_share"])
                        if row["share_transfer_per_share"] else ZERO
                    ),
                )
        )
    return tuple(actions)


def load_sessions(path: str | Path) -> tuple[Session, ...]:
    sessions: list[Session] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            close = dec(row["close"]) if row["close"] else None
            sessions.append(
                Session(
                    session_date=required_date(row["session_date"], "session_date"),
                    close=close,
                    trade_status=row["trade_status"],
                    limit_up=dec(row["limit_up"]) if row["limit_up"] else None,
                    limit_down=dec(row["limit_down"]) if row["limit_down"] else None,
                )
            )
    return tuple(sessions)


__all__ = [
    "Account", "CorporateAction", "DailyCloseLaggedEngine", "DailySnapshot",
    "DataGateError", "DividendTaxRule", "DividendTaxSchedule", "FeeBreakdown",
    "FeeRule", "FillResult", "HDAnchorStrategy", "OrderInstruction",
    "PITDividendRecord", "PITDividendSelector", "ReconciliationError",
    "Session", "Stage8Error", "StrategyConfig", "StrategyDecision",
    "TransactionCostSchedule", "account_amount", "add_calendar_months",
    "add_calendar_years", "dec", "fee_amount", "initialize_research_account",
    "load_corporate_actions", "load_sessions", "parse_date", "parse_datetime", "required_date",
    "shanghai_close",
]
