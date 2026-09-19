"""Research-only risk bridge to the indexed Sartre snapshot.

The caller adds the verified snapshot to sys.path and supplies a fresh, complete
account loader. This module neither constructs a broker nor queries any API.
"""
from dataclasses import replace

from sartre_core.engine import SignalAction
from sartre_core.engine.context import SymbolPosition
from sartre_risk import RiskManager
from sartre_risk.risk_manager import RiskCheckResult

from etf_execution_repairs_v1 import FullAccountGuard


class ResearchRiskManager(RiskManager):
    def __init__(self, config, *, guard: FullAccountGuard, snapshot_loader):
        # Always enforce broker/ledger available volume, including mixed T0/T1.
        super().__init__(replace(config, enable_t1=True))
        self.guard = guard
        self.snapshot_loader = snapshot_loader

    def check_and_adjust(self, signal, context, market=None, operation_key=None):
        if signal.action == SignalAction.HOLD:
            return super().check_and_adjust(signal, context, market, operation_key)
        try:
            signal.validate()
            snapshot = self.snapshot_loader()
            if not snapshot.complete:
                raise ValueError("incomplete_account_or_order_state")
            # Refresh full positions at the risk decision, not from a per-symbol
            # context or an earlier target map. No pending SELL is netted away.
            context.positions = {p.symbol: SymbolPosition(
                symbol=p.symbol, volume=p.volume, available_volume=p.available,
                market_value=float(p.market_value)) for p in snapshot.positions}
            context.positions.setdefault(signal.symbol, SymbolPosition(signal.symbol))
            context.total_asset = float(min(snapshot.equity, self.guard.limits.capital_cap))
            context.available_cash = float(min(snapshot.available_cash, self.guard.limits.capital_cap))
            context.sync_legacy_fields(signal.symbol)
            if signal.action == SignalAction.BUY:
                price = self._resolve_price(signal, market)
                plan = self.guard.plan_buy(snapshot, signal.symbol, price,
                    target_pct=signal.target_pct, target_volume=signal.target_volume)
                if not plan.allowed:
                    return RiskCheckResult(False, self._to_hold(signal, plan.reason), plan.reason)
                signal = replace(signal, target_volume=plan.target_volume)
            result = super().check_and_adjust(signal, context, market, operation_key)
            if signal.action == SignalAction.BUY and result.ok:
                # Legacy target rounding may only reduce this guarded increment.
                # Refuse an odd increment rather than submit an invalid lot.
                delta = result.signal.target_volume - context.get_position(signal.symbol).volume
                lot = self.guard.instruments[signal.symbol].lot_size
                if delta <= 0 or delta % lot or delta > plan.delta:
                    return RiskCheckResult(False, self._to_hold(signal, "bridge_volume_mismatch"), "bridge_volume_mismatch")
                result.adjustments.update({"full_account_guard": True,
                    "fee_reserve": str(plan.fee_reserve), "cash_reserve": str(plan.cash_reserve),
                    "capital_basis_after_unbooked_fees": str(plan.capital_basis)})
            return result
        except Exception as exc:
            return RiskCheckResult(False, self._to_hold(signal, "research_state_unavailable"),
                                   "research_state_unavailable:" + str(exc))
