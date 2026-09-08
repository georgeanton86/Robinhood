"""Strategy interface.

A strategy is a pure function of market data (+ optional sentiment) to a list of
:class:`Signal` objects. Strategies do NOT know about brokers, cash, or position
sizing — that's the risk manager's and engine's job. This separation keeps each
strategy small, testable, and swappable (the "pluggable framework" idea).
"""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from ..data.market_data import MarketDataProvider
from ..data.sentiment import SentimentProvider


class SignalAction(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    symbol: str
    action: SignalAction
    strength: float = 1.0  # 0..1 — how strong the conviction is
    reason: str = ""


@dataclass
class StrategyContext:
    """Everything a strategy is allowed to see when deciding."""

    symbols: List[str]
    data: MarketDataProvider
    sentiment: Optional[SentimentProvider] = None


class Strategy(ABC):
    name: str = "strategy"

    @abstractmethod
    def generate_signals(self, ctx: StrategyContext) -> List[Signal]:
        ...
