"""Momentum + sentiment strategy.

Same momentum core, but a trade is only taken when price momentum AND news
sentiment agree. The idea (matching the "momentum and sentiment agent" design):
don't buy a dip that the news says is justified, and don't fade strength that
the news supports. Works on ETFs (SPY/QQQ) or a tech-stock universe.

Sentiment is only as good as the feed behind it — the default provider is
neutral (0.0), which makes this behave like plain momentum until you wire in a
real news source.
"""
from __future__ import annotations

from typing import List

from .base import Signal, SignalAction, Strategy, StrategyContext
from .momentum import MomentumStrategy


class MomentumSentimentStrategy(Strategy):
    name = "momentum_sentiment"

    def __init__(self, lookback: int = 10, threshold: float = 0.001,
                 sentiment_weight: float = 0.5, min_sentiment: float = -0.1):
        self._momentum = MomentumStrategy(lookback=lookback, threshold=threshold)
        self.sentiment_weight = float(sentiment_weight)
        self.min_sentiment = float(min_sentiment)

    def generate_signals(self, ctx: StrategyContext) -> List[Signal]:
        base_signals = self._momentum.generate_signals(ctx)
        if ctx.sentiment is None:
            return base_signals

        out: List[Signal] = []
        for sig in base_signals:
            score = ctx.sentiment.get_sentiment(sig.symbol)

            if sig.action == SignalAction.BUY:
                if score < self.min_sentiment:
                    # Momentum up but news clearly negative -> stand aside.
                    out.append(Signal(sig.symbol, SignalAction.HOLD, 0.0,
                                      f"{sig.reason}; blocked by sentiment={score:.2f}"))
                else:
                    boosted = min(1.0, sig.strength * (1 + self.sentiment_weight * max(0.0, score)))
                    out.append(Signal(sig.symbol, SignalAction.BUY, boosted,
                                      f"{sig.reason}; sentiment={score:.2f}"))
            elif sig.action == SignalAction.SELL:
                out.append(Signal(sig.symbol, SignalAction.SELL, sig.strength,
                                  f"{sig.reason}; sentiment={score:.2f}"))
            else:
                out.append(sig)
        return out
