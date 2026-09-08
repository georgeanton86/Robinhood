"""Broker abstraction.

Every broker (the offline simulator, a real Alpaca paper account, and — if you
ever deliberately enable it — a live account) implements the same
:class:`BrokerAdapter` interface, so strategies and the engine never care which
one they're talking to. This is what keeps the risky part (real money) isolated
behind a single, auditable seam.
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    symbol: str
    qty: float
    side: OrderSide
    filled_price: Optional[float] = None
    status: str = "new"
    reason: str = ""
    id: Optional[str] = None


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float

    def market_value(self, price: float) -> float:
        return self.qty * price

    def unrealized_pl(self, price: float) -> float:
        return (price - self.avg_entry_price) * self.qty


@dataclass
class Account:
    cash: float
    equity: float
    positions: Dict[str, Position] = field(default_factory=dict)
    # Whether this account trades fake money. The engine hard-checks this.
    is_paper: bool = True


class BrokerAdapter(ABC):
    """Interface every broker implementation must satisfy."""

    #: True if this adapter can never move real money.
    is_paper: bool = True

    @abstractmethod
    def get_account(self) -> Account:
        ...

    @abstractmethod
    def get_positions(self) -> List[Position]:
        ...

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        ...

    @abstractmethod
    def is_market_open(self) -> bool:
        ...

    @abstractmethod
    def submit_order(self, symbol: str, qty: float, side: OrderSide, reason: str = "") -> Order:
        ...

    def close_position(self, symbol: str, reason: str = "") -> Optional[Order]:
        for pos in self.get_positions():
            if pos.symbol == symbol and pos.qty != 0:
                side = OrderSide.SELL if pos.qty > 0 else OrderSide.BUY
                return self.submit_order(symbol, abs(pos.qty), side, reason=reason)
        return None
