"""Price-bar providers behind one interface.

- ``SyntheticData``: deterministic offline bars (geometric random walk). Needs
  no network or keys — used by tests, demos, and offline backtests.
- ``YFinanceData``: real historical/recent bars via yfinance (optional dep).

Each ``get_bars`` returns a pandas DataFrame indexed by timestamp with at least
a ``close`` column (and open/high/low/volume where available).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, lookback: int, timeframe: str = "1Min") -> pd.DataFrame:
        ...

    def get_last_price(self, symbol: str) -> float:
        bars = self.get_bars(symbol, lookback=1)
        if bars.empty:
            raise ValueError(f"No bars available for {symbol}")
        return float(bars["close"].iloc[-1])


class SyntheticData(MarketDataProvider):
    """Deterministic synthetic bars. Same symbol+seed => same series, so tests
    and backtests are reproducible. Not a market forecast — just a sane price
    path for exercising the plumbing."""

    def __init__(self, seed: int = 42, start_price: float = 400.0,
                 drift: float = 0.0002, vol: float = 0.004, n: int = 500):
        self._seed = seed
        self._start_price = start_price
        self._drift = drift
        self._vol = vol
        self._n = n
        self._cache: dict[str, pd.DataFrame] = {}

    def _series(self, symbol: str) -> pd.DataFrame:
        if symbol in self._cache:
            return self._cache[symbol]
        # Seed per-symbol so different tickers get different (but stable) paths.
        sym_seed = self._seed + sum(ord(c) for c in symbol.upper())
        rng = np.random.default_rng(sym_seed)
        shocks = rng.normal(self._drift, self._vol, self._n)
        prices = self._start_price * np.exp(np.cumsum(shocks))
        idx = pd.date_range("2024-01-01 09:00", periods=self._n, freq="1min")
        df = pd.DataFrame(
            {
                "open": prices,
                "high": prices * (1 + rng.uniform(0, self._vol, self._n)),
                "low": prices * (1 - rng.uniform(0, self._vol, self._n)),
                "close": prices,
                "volume": rng.integers(1_000, 100_000, self._n),
            },
            index=idx,
        )
        self._cache[symbol] = df
        return df

    def get_bars(self, symbol: str, lookback: int, timeframe: str = "1Min") -> pd.DataFrame:
        df = self._series(symbol)
        return df.tail(max(1, lookback)).copy()

    def full_series(self, symbol: str) -> pd.DataFrame:
        """Whole synthetic history — handy for backtests."""
        return self._series(symbol).copy()


class YFinanceData(MarketDataProvider):  # pragma: no cover - needs network
    """Real bars via yfinance. Optional dependency."""

    _INTERVAL = {"1Min": "1m", "5Min": "5m", "15Min": "15m", "1Day": "1d"}

    def __init__(self):
        try:
            import yfinance  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "yfinance is not installed. Run `pip install yfinance`, or use "
                "SyntheticData for offline runs."
            ) from exc

    def get_bars(self, symbol: str, lookback: int, timeframe: str = "1Min") -> pd.DataFrame:
        import yfinance as yf

        interval = self._INTERVAL.get(timeframe, "1m")
        period = "5d" if interval.endswith("m") else "6mo"
        raw = yf.Ticker(symbol).history(period=period, interval=interval)
        if raw.empty:
            return raw
        raw = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        return raw.tail(max(1, lookback))


def get_provider(name: str = "synthetic", **kwargs) -> MarketDataProvider:
    name = (name or "synthetic").lower()
    if name in {"synthetic", "sim"}:
        return SyntheticData(**kwargs)
    if name in {"yfinance", "yahoo"}:
        return YFinanceData()
    raise ValueError(f"Unknown data provider: {name}")
