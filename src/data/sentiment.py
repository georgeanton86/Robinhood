"""News/sentiment scoring, pluggable behind one interface.

``get_sentiment(symbol)`` returns a score in [-1, 1]: negative = bearish news,
positive = bullish. The default ``NeutralSentiment`` returns 0.0 and needs
nothing — good for offline runs and tests. To trade on real sentiment (live),
plug in a provider backed by a real news/LLM feed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class SentimentProvider(ABC):
    @abstractmethod
    def get_sentiment(self, symbol: str) -> float:
        """Return a sentiment score in [-1.0, 1.0]."""
        ...


class NeutralSentiment(SentimentProvider):
    """Always neutral. Use when you have no news feed configured."""

    def get_sentiment(self, symbol: str) -> float:
        return 0.0


class KeywordSentiment(SentimentProvider):
    """Toy offline provider: scores prewritten headlines by keyword. Useful for
    demos and tests — NOT a real signal. Replace for live trading."""

    _POS = {"beats", "surges", "record", "upgrade", "growth", "rally", "strong"}
    _NEG = {"misses", "plunges", "lawsuit", "downgrade", "recall", "probe", "weak"}

    def __init__(self, headlines: dict[str, list[str]] | None = None):
        self._headlines = {k.upper(): v for k, v in (headlines or {}).items()}

    def get_sentiment(self, symbol: str) -> float:
        heads = self._headlines.get(symbol.upper(), [])
        if not heads:
            return 0.0
        score = 0
        for h in heads:
            words = {w.strip(".,!?").lower() for w in h.split()}
            score += len(words & self._POS) - len(words & self._NEG)
        return max(-1.0, min(1.0, score / max(1, len(heads))))


def get_sentiment_provider(kind: str = "neutral", **kwargs) -> SentimentProvider:
    kind = (kind or "neutral").lower()
    if kind == "neutral":
        return NeutralSentiment()
    if kind == "keyword":
        return KeywordSentiment(**kwargs)
    raise ValueError(f"Unknown sentiment provider: {kind}")
