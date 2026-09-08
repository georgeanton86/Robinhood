from .base import Signal, SignalAction, Strategy, StrategyContext
from .momentum import MomentumStrategy
from .momentum_sentiment import MomentumSentimentStrategy

STRATEGIES = {
    "momentum": MomentumStrategy,
    "momentum_sentiment": MomentumSentimentStrategy,
}

__all__ = [
    "Signal",
    "SignalAction",
    "Strategy",
    "StrategyContext",
    "MomentumStrategy",
    "MomentumSentimentStrategy",
    "STRATEGIES",
]
