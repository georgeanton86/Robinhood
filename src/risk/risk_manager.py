"""Risk manager — turns strategy signals into safe, sized orders.

This is deliberately the most conservative part of the system. It:
  * caps how much of the account any one position or the whole book can use,
  * limits the number of open positions,
  * halts trading for the day after a max drawdown (the single most important
    control — it stops a bad day from becoming a catastrophe),
  * applies per-position stop-loss / take-profit exits.

Strategies propose; the risk manager disposes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..brokers.base import Account, OrderSide, Position
from ..strategies.base import Signal, SignalAction


@dataclass
class RiskDecision:
    symbol: str
    side: OrderSide
    qty: float
    reason: str


class RiskManager:
    def __init__(
        self,
        max_position_pct: float = 0.20,
        max_total_exposure_pct: float = 1.0,
        max_daily_loss_pct: float = 0.03,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.04,
        max_open_positions: int = 4,
        allow_fractional: bool = False,
        min_order_notional: float = 1.0,
        trailing_stop_pct: float = 0.0,
    ):
        self.max_position_pct = max_position_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_open_positions = max_open_positions
        # Fractional shares let a tiny account (e.g. $10) actually place trades,
        # since a single share of SPY/QQQ costs far more than $10.
        self.allow_fractional = allow_fractional
        self.min_order_notional = min_order_notional
        # Trailing stop: exit if price falls this % from its peak since entry.
        # This is the "lock in part of the gain" idea. 0 disables it.
        self.trailing_stop_pct = trailing_stop_pct

        self._day_start_equity: Optional[float] = None
        self._halted = False
        self._peak: Dict[str, float] = {}  # highest price seen per open position

    # --- daily loss guard -------------------------------------------------
    def start_day(self, equity: float) -> None:
        self._day_start_equity = equity
        self._halted = False

    def update_and_check_halt(self, equity: float) -> bool:
        """Return True if trading is halted for the day."""
        if self._day_start_equity is None:
            self._day_start_equity = equity
        drawdown = (self._day_start_equity - equity) / self._day_start_equity
        if drawdown >= self.max_daily_loss_pct:
            self._halted = True
        return self._halted

    @property
    def halted(self) -> bool:
        return self._halted

    # --- protective exits -------------------------------------------------
    def protective_exits(self, account: Account, prices: Dict[str, float]) -> List[RiskDecision]:
        """Stop-loss / take-profit / trailing-stop exits, before new entries."""
        exits: List[RiskDecision] = []
        held = set(account.positions)
        # Forget peaks for positions we no longer hold.
        for sym in [s for s in self._peak if s not in held]:
            del self._peak[sym]

        for sym, pos in account.positions.items():
            price = prices.get(sym)
            if price is None or pos.qty == 0:
                continue
            # Track the high-water mark since we entered this position.
            peak = max(self._peak.get(sym, pos.avg_entry_price), price)
            self._peak[sym] = peak

            ret = (price - pos.avg_entry_price) / pos.avg_entry_price
            drop_from_peak = (peak - price) / peak if peak > 0 else 0.0

            if self.trailing_stop_pct > 0 and drop_from_peak >= self.trailing_stop_pct:
                # Locks in gains once we're up, and caps losses if we never got up.
                exits.append(RiskDecision(sym, OrderSide.SELL, abs(pos.qty),
                                          f"trailing-stop: -{drop_from_peak:.3f} from peak "
                                          f"(P/L {ret:+.3f})"))
            elif ret <= -self.stop_loss_pct:
                exits.append(RiskDecision(sym, OrderSide.SELL, abs(pos.qty),
                                          f"stop-loss {ret:.3f} <= -{self.stop_loss_pct}"))
            elif ret >= self.take_profit_pct:
                exits.append(RiskDecision(sym, OrderSide.SELL, abs(pos.qty),
                                          f"take-profit {ret:.3f} >= {self.take_profit_pct}"))
        return exits

    # --- sizing new entries ----------------------------------------------
    def size_orders(
        self,
        signals: List[Signal],
        account: Account,
        prices: Dict[str, float],
    ) -> List[RiskDecision]:
        if self._halted:
            return []

        decisions: List[RiskDecision] = []
        equity = account.equity
        open_positions = {s: p for s, p in account.positions.items() if p.qty != 0}
        current_exposure = sum(
            abs(p.market_value(prices.get(s, p.avg_entry_price)))
            for s, p in open_positions.items()
        )
        cash_available = account.cash

        for sig in signals:
            price = prices.get(sig.symbol)
            if price is None or price <= 0:
                continue

            held = open_positions.get(sig.symbol)

            if sig.action == SignalAction.SELL:
                if held and held.qty > 0:
                    decisions.append(RiskDecision(sig.symbol, OrderSide.SELL, held.qty,
                                                  f"signal sell: {sig.reason}"))
                continue

            if sig.action != SignalAction.BUY:
                continue
            if held and held.qty > 0:
                continue  # already in the position; don't pyramid
            if len(open_positions) + len(
                [d for d in decisions if d.side == OrderSide.BUY]
            ) >= self.max_open_positions:
                continue

            # Position size = min(per-position cap, remaining exposure cap, cash),
            # scaled by the signal's conviction.
            per_pos_cap = equity * self.max_position_pct
            exposure_room = max(0.0, equity * self.max_total_exposure_pct - current_exposure)
            budget = min(per_pos_cap, exposure_room, cash_available) * max(0.0, min(1.0, sig.strength))
            if self.allow_fractional:
                # Buy a fractional share worth `budget`, if it clears the broker's
                # minimum order size.
                if budget < self.min_order_notional:
                    continue
                qty = round(budget / price, 6)
            else:
                qty = int(budget // price)
            if qty <= 0:
                continue

            current_exposure += qty * price
            cash_available -= qty * price
            decisions.append(RiskDecision(sig.symbol, OrderSide.BUY, qty,
                                          f"signal buy (size {qty}): {sig.reason}"))
        return decisions
