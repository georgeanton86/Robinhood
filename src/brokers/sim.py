"""SimBroker — a pure in-memory broker simulation.

Needs no account, no API keys, and no network. It fills market orders at a
price you feed in (from synthetic or historical data), tracks cash/positions,
and can never touch real money. This is the default for learning, tests, and
backtests.
"""
from __future__ import annotations

import itertools
from typing import Dict, List

from .base import Account, BrokerAdapter, Order, OrderSide, Position


class SimBroker(BrokerAdapter):
    is_paper = True

    def __init__(self, starting_cash: float = 30_000.0, commission: float = 0.0):
        self._cash = float(starting_cash)
        self._commission = float(commission)
        self._positions: Dict[str, Position] = {}
        self._last_prices: Dict[str, float] = {}
        self._orders: List[Order] = []
        self._ids = itertools.count(1)

    # --- price feed -------------------------------------------------------
    def set_price(self, symbol: str, price: float) -> None:
        """Feed the current price (called by the engine/backtest each tick)."""
        self._last_prices[symbol.upper()] = float(price)

    def get_price(self, symbol: str) -> float:
        price = self._last_prices.get(symbol.upper())
        if price is None:
            raise ValueError(f"No price set for {symbol}. Call set_price() first.")
        return price

    # --- account ----------------------------------------------------------
    def get_account(self) -> Account:
        return Account(
            cash=self._cash,
            equity=self.equity(),
            positions=dict(self._positions),
            is_paper=True,
        )

    def equity(self) -> float:
        holdings = 0.0
        for sym, pos in self._positions.items():
            price = self._last_prices.get(sym, pos.avg_entry_price)
            holdings += pos.market_value(price)
        return self._cash + holdings

    def get_positions(self) -> List[Position]:
        return [p for p in self._positions.values() if p.qty != 0]

    def is_market_open(self) -> bool:
        # The simulator is always "open"; the engine controls the schedule.
        return True

    # --- orders -----------------------------------------------------------
    def submit_order(self, symbol: str, qty: float, side: OrderSide, reason: str = "") -> Order:
        symbol = symbol.upper()
        qty = abs(float(qty))
        price = self.get_price(symbol)
        order = Order(symbol=symbol, qty=qty, side=side, reason=reason, id=str(next(self._ids)))

        if qty <= 0:
            order.status = "rejected"
            self._orders.append(order)
            return order

        cost = qty * price + self._commission
        pos = self._positions.get(symbol)

        if side == OrderSide.BUY:
            if cost > self._cash + 1e-9:
                order.status = "rejected"
                order.reason = (reason + " | insufficient cash").strip(" |")
                self._orders.append(order)
                return order
            self._cash -= cost
            if pos and pos.qty > 0:
                total_qty = pos.qty + qty
                pos.avg_entry_price = (pos.avg_entry_price * pos.qty + price * qty) / total_qty
                pos.qty = total_qty
            else:
                self._positions[symbol] = Position(symbol, qty, price)
        else:  # SELL
            held = pos.qty if pos else 0.0
            sell_qty = min(qty, held)  # long-only simulator: no shorting
            if sell_qty <= 0:
                order.status = "rejected"
                order.reason = (reason + " | no shares to sell").strip(" |")
                self._orders.append(order)
                return order
            self._cash += sell_qty * price - self._commission
            pos.qty -= sell_qty
            order.qty = sell_qty
            if pos.qty <= 1e-9:
                del self._positions[symbol]

        order.filled_price = price
        order.status = "filled"
        self._orders.append(order)
        return order

    @property
    def orders(self) -> List[Order]:
        return list(self._orders)
