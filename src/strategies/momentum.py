"""Momentum strategy.

Classic short-window momentum: measure the recent return of each symbol over a
lookback window and go long when it's rising faster than a threshold, exit when
momentum turns negative. Mirrors the common "10-minute momentum on SPY/QQQ"
design — but remember: short-window momentum is one of the *hardest* edges to
capture profitably after costs. Prove it in paper first.
"""
from __future__ import annotations

from typing import List

from .base import Signal, SignalAction, Strategy, StrategyContext


class MomentumStrategy(Strategy):
    name = "momentum"

    def __init__(self, lookback: int = 10, threshold: float = 0.001):
        self.lookback = max(2, int(lookback))
        self.threshold = float(threshold)

    def _momentum(self, closes) -> float:
        if len(closes) < 2:
            return 0.0
        first, last = float(closes.iloc[0]), float(closes.iloc[-1])
        if first == 0:
            return 0.0
        return (last - first) / first

    def generate_signals(self, ctx: StrategyContext) -> List[Signal]:
        signals: List[Signal] = []
        for symbol in ctx.symbols:
            bars = ctx.data.get_bars(symbol, lookback=self.lookback)
            if bars.empty or len(bars) < self.lookback:
                signals.append(Signal(symbol, SignalAction.HOLD, 0.0, "insufficient data"))
                continue

            mom = self._momentum(bars["close"])
            if mom > self.threshold:
                # Scale conviction by how far past the threshold we are. When the
                # threshold is 0, fall back to full conviction on any positive momentum.
                scale = self.threshold * 10
                strength = min(1.0, mom / scale) if scale > 0 else 1.0
                signals.append(
                    Signal(symbol, SignalAction.BUY, strength, f"momentum={mom:.4f} > {self.threshold}")
                )
            elif mom < -self.threshold:
                signals.append(
                    Signal(symbol, SignalAction.SELL, 1.0, f"momentum={mom:.4f} < -{self.threshold}")
                )
            else:
                signals.append(Signal(symbol, SignalAction.HOLD, 0.0, f"momentum={mom:.4f} flat"))
        return signals
