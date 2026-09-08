"""TradingEngine — the live/paper decision loop.

Each cycle it:
  1. refreshes prices,
  2. checks the daily-loss halt,
  3. runs protective exits (stop-loss/take-profit),
  4. asks the strategy for signals,
  5. sizes them through the risk manager,
  6. submits the resulting orders through the broker.

A hard safety check refuses to run against a non-paper broker unless the
operator has explicitly opted in to live trading in config.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from ..brokers.base import BrokerAdapter, Order
from ..data.market_data import MarketDataProvider
from ..data.sentiment import SentimentProvider
from ..risk.risk_manager import RiskManager
from ..strategies.base import Strategy, StrategyContext

log = logging.getLogger("engine")


class TradingEngine:
    def __init__(
        self,
        broker: BrokerAdapter,
        data: MarketDataProvider,
        strategy: Strategy,
        risk: RiskManager,
        symbols: List[str],
        *,
        sentiment: Optional[SentimentProvider] = None,
        allow_live: bool = False,
        market_timezone: str = "America/Chicago",
        window_start=None,
        window_end=None,
    ):
        # --- the guard rail: never trade real money by accident -----------
        if not broker.is_paper and not allow_live:
            raise RuntimeError(
                "Refusing to run: broker is LIVE but live trading is not enabled. "
                "Set TRADING_MODE=live and ALLOW_LIVE_TRADING=YES_I_UNDERSTAND_THE_RISKS "
                "only after you fully understand the risk. Staying safe."
            )

        self.broker = broker
        self.data = data
        self.strategy = strategy
        self.risk = risk
        self.symbols = [s.upper() for s in symbols]
        self.sentiment = sentiment
        self.allow_live = allow_live
        self.tz = ZoneInfo(market_timezone)
        self.window_start = window_start
        self.window_end = window_end

        acct = self.broker.get_account()
        self.risk.start_day(acct.equity)
        mode = "LIVE (real money)" if (not broker.is_paper and allow_live) else "paper/simulated"
        log.info("Engine initialized in %s mode. Starting equity: %.2f", mode, acct.equity)

    # --- schedule ---------------------------------------------------------
    def within_window(self, now: Optional[datetime] = None) -> bool:
        if self.window_start is None or self.window_end is None:
            return True
        now = now or datetime.now(self.tz)
        return self.window_start <= now.timetz().replace(tzinfo=None) <= self.window_end

    # --- prices -----------------------------------------------------------
    def _refresh_prices(self) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for sym in self.symbols:
            try:
                prices[sym] = self.data.get_last_price(sym)
            except Exception as exc:  # keep going for other symbols
                log.warning("No price for %s: %s", sym, exc)
        # If the broker is a simulator, feed it the prices so fills are consistent.
        setter = getattr(self.broker, "set_price", None)
        if callable(setter):
            for sym, price in prices.items():
                setter(sym, price)
        return prices

    # --- one decision cycle ----------------------------------------------
    def run_cycle(self, now: Optional[datetime] = None) -> List[Order]:
        placed: List[Order] = []
        prices = self._refresh_prices()
        if not prices:
            return placed

        account = self.broker.get_account()

        if self.risk.update_and_check_halt(account.equity):
            log.warning("Daily loss limit hit — trading halted for the day.")
            return placed

        if not self.within_window(now):
            log.debug("Outside trading window; skipping entries.")
            # Protective exits still run below even outside the window.

        # 1) protective exits first
        for exit_ in self.risk.protective_exits(account, prices):
            order = self.broker.submit_order(exit_.symbol, exit_.qty, exit_.side, exit_.reason)
            placed.append(order)
            log.info("EXIT %s %s x%s @ %s (%s)", exit_.side.value, exit_.symbol,
                     exit_.qty, order.filled_price, exit_.reason)

        # 2) new entries only inside the trading window
        if self.within_window(now):
            ctx = StrategyContext(symbols=self.symbols, data=self.data, sentiment=self.sentiment)
            signals = self.strategy.generate_signals(ctx)
            account = self.broker.get_account()  # refresh after exits
            for decision in self.risk.size_orders(signals, account, prices):
                order = self.broker.submit_order(
                    decision.symbol, decision.qty, decision.side, decision.reason
                )
                placed.append(order)
                log.info("ORDER %s %s x%s @ %s (%s)", decision.side.value, decision.symbol,
                         decision.qty, order.filled_price, decision.reason)
        return placed
