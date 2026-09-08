"""AlpacaBroker — real Alpaca account adapter.

Defaults to Alpaca's **paper** endpoint (fake money). It will only talk to the
live endpoint if the caller passes ``paper=False`` AND the operator has opted in
via config — the engine enforces that. Requires ``alpaca-py`` and API keys;
without them, use :class:`~src.brokers.sim.SimBroker` instead.
"""
from __future__ import annotations

from typing import List

from .base import Account, BrokerAdapter, Order, OrderSide, Position

PAPER_URL = "https://paper-api.alpaca.markets"


class AlpacaBroker(BrokerAdapter):
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        if not api_key or not secret_key:
            raise ValueError(
                "Alpaca API keys are required. Get free PAPER keys at "
                "https://alpaca.markets and set them in your .env."
            )
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "alpaca-py is not installed. Run `pip install alpaca-py`, or use "
                "the SimBroker (`--broker sim`) which needs no dependencies."
            ) from exc

        self.is_paper = bool(paper)
        self._client = TradingClient(api_key, secret_key, paper=paper)

    def get_account(self) -> Account:
        acct = self._client.get_account()
        positions = {p.symbol: p for p in self.get_positions()}
        return Account(
            cash=float(acct.cash),
            equity=float(acct.equity),
            positions=positions,
            is_paper=self.is_paper,
        )

    def get_positions(self) -> List[Position]:
        out: List[Position] = []
        for p in self._client.get_all_positions():
            out.append(
                Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    avg_entry_price=float(p.avg_entry_price),
                )
            )
        return out

    def get_price(self, symbol: str) -> float:
        # Prefer a dedicated data provider; fall back to the position's price.
        for p in self._client.get_all_positions():
            if p.symbol == symbol.upper():
                return float(p.current_price)
        raise ValueError(
            f"No live price available for {symbol} from the trading client; "
            "use a MarketDataProvider for quotes."
        )

    def is_market_open(self) -> bool:
        return bool(self._client.get_clock().is_open)

    def submit_order(self, symbol: str, qty: float, side: OrderSide, reason: str = "") -> Order:
        from alpaca.trading.enums import OrderSide as AlpacaSide
        from alpaca.trading.enums import TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        req = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=abs(float(qty)),
            side=AlpacaSide.BUY if side == OrderSide.BUY else AlpacaSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        resp = self._client.submit_order(order_data=req)
        return Order(
            symbol=symbol.upper(),
            qty=abs(float(qty)),
            side=side,
            status=str(getattr(resp, "status", "submitted")),
            reason=reason,
            id=str(getattr(resp, "id", "")),
        )
