"""Event-driven backtester.

Replays historical (or synthetic) bars one step at a time, running the SAME
strategy / risk / broker code path the live engine uses, and reports an equity
curve plus summary stats. Because it reuses the real components, a strategy that
behaves in backtest behaves the same in paper.

Reminder: a good backtest is necessary but nowhere near sufficient. Overfitting,
survivorship bias, look-ahead bias, slippage, and regime change all make
backtests look rosier than reality. Treat a good result as "worth paper-testing",
never as "this will make money".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.brokers.sim import SimBroker
from src.data.market_data import MarketDataProvider, SyntheticData
from src.data.sentiment import SentimentProvider
from src.engine.trading_engine import TradingEngine
from src.risk.risk_manager import RiskManager
from src.strategies.base import Strategy


class _WindowedData(MarketDataProvider):
    """Exposes only the bars up to the current backtest index (no look-ahead)."""

    def __init__(self, series: Dict[str, pd.DataFrame]):
        self._series = {k.upper(): v for k, v in series.items()}
        self._i = 0
        self.length = min(len(v) for v in self._series.values())

    def set_index(self, i: int) -> None:
        self._i = i

    def get_bars(self, symbol: str, lookback: int, timeframe: str = "1Min") -> pd.DataFrame:
        df = self._series[symbol.upper()]
        start = max(0, self._i - lookback + 1)
        return df.iloc[start : self._i + 1].copy()

    def get_last_price(self, symbol: str) -> float:
        return float(self._series[symbol.upper()]["close"].iloc[self._i])

    def timestamp(self) -> pd.Timestamp:
        any_df = next(iter(self._series.values()))
        return any_df.index[self._i]


@dataclass
class BacktestResult:
    equity_curve: List[float]
    timestamps: List[pd.Timestamp]
    starting_equity: float
    ending_equity: float
    total_return: float
    max_drawdown: float
    sharpe: float
    num_trades: int

    def summary(self) -> str:
        return (
            f"Starting equity : ${self.starting_equity:,.2f}\n"
            f"Ending equity   : ${self.ending_equity:,.2f}\n"
            f"Total return    : {self.total_return * 100:+.2f}%\n"
            f"Max drawdown    : {self.max_drawdown * 100:.2f}%\n"
            f"Sharpe (per-bar): {self.sharpe:.2f}\n"
            f"Trades filled   : {self.num_trades}"
        )


def run_backtest(
    strategy: Strategy,
    symbols: List[str],
    *,
    data: Optional[MarketDataProvider] = None,
    sentiment: Optional[SentimentProvider] = None,
    starting_cash: float = 30_000.0,
    risk: Optional[RiskManager] = None,
    warmup: int = 15,
    commission: float = 0.0,
) -> BacktestResult:
    symbols = [s.upper() for s in symbols]
    src = data if isinstance(data, SyntheticData) else SyntheticData()
    series = {sym: src.full_series(sym) for sym in symbols}

    windowed = _WindowedData(series)
    broker = SimBroker(starting_cash=starting_cash, commission=commission)
    risk = risk or RiskManager()

    engine = TradingEngine(
        broker=broker,
        data=windowed,
        strategy=strategy,
        risk=risk,
        symbols=symbols,
        sentiment=sentiment,
        allow_live=False,
        window_start=None,  # backtest ignores time-of-day gating
        window_end=None,
    )

    equity_curve: List[float] = []
    timestamps: List[pd.Timestamp] = []
    current_date = None

    for i in range(warmup, windowed.length):
        windowed.set_index(i)
        ts = windowed.timestamp()
        if current_date != ts.date():
            current_date = ts.date()
            risk.start_day(broker.equity())  # reset daily-loss guard each day
        engine.run_cycle(now=None)
        equity_curve.append(broker.equity())
        timestamps.append(ts)

    eq = np.array(equity_curve, dtype=float)
    start_eq = starting_cash
    end_eq = float(eq[-1]) if len(eq) else start_eq
    total_return = (end_eq - start_eq) / start_eq

    running_max = np.maximum.accumulate(eq) if len(eq) else np.array([start_eq])
    drawdowns = (running_max - eq) / running_max
    max_dd = float(np.max(drawdowns)) if len(drawdowns) else 0.0

    rets = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([0.0])
    sharpe = float(np.mean(rets) / np.std(rets)) if np.std(rets) > 0 else 0.0

    num_trades = sum(1 for o in broker.orders if o.status == "filled")

    return BacktestResult(
        equity_curve=equity_curve,
        timestamps=timestamps,
        starting_equity=start_eq,
        ending_equity=end_eq,
        total_return=total_return,
        max_drawdown=max_dd,
        sharpe=sharpe,
        num_trades=num_trades,
    )
