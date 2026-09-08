"""Central configuration, loaded from environment with safe defaults.

The most important thing this module does is enforce the *paper-first* safety
rule: live (real money) trading is only allowed when the operator sets both
``TRADING_MODE=live`` and the exact opt-in phrase in ``ALLOW_LIVE_TRADING``.
Anything short of that resolves to paper mode.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from typing import List

try:
    # Optional: load a local .env if python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


LIVE_OPT_IN_PHRASE = "YES_I_UNDERSTAND_THE_RISKS"


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _parse_time(value: str, default: time) -> time:
    try:
        hh, mm = value.strip().split(":")
        return time(int(hh), int(mm))
    except Exception:
        return default


def _parse_symbols(value: str) -> List[str]:
    return [s.strip().upper() for s in value.replace(";", ",").split(",") if s.strip()]


@dataclass
class RiskConfig:
    starting_cash: float = 30_000.0
    max_position_pct: float = 0.20
    max_total_exposure_pct: float = 1.0
    max_daily_loss_pct: float = 0.03
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_open_positions: int = 4


@dataclass
class StrategyConfig:
    momentum_lookback: int = 10
    momentum_threshold: float = 0.001


@dataclass
class Settings:
    mode: str = "paper"  # backtest | paper | live
    live_allowed: bool = False

    symbols: List[str] = field(default_factory=lambda: ["SPY", "QQQ"])
    market_timezone: str = "America/Chicago"
    trade_window_start: time = time(9, 0)
    trade_window_end: time = time(11, 0)
    loop_interval_seconds: int = 60

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    news_api_key: str = ""

    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)

    @property
    def is_live(self) -> bool:
        """True only if the operator explicitly and correctly opted in."""
        return self.mode == "live" and self.live_allowed

    @property
    def effective_mode(self) -> str:
        """The mode that will actually run — never 'live' without opt-in."""
        if self.mode == "live" and not self.live_allowed:
            return "paper"
        return self.mode


def load_settings() -> Settings:
    requested_mode = _get("TRADING_MODE", "paper").strip().lower()
    if requested_mode not in {"backtest", "paper", "live"}:
        requested_mode = "paper"

    live_allowed = _get("ALLOW_LIVE_TRADING", "").strip() == LIVE_OPT_IN_PHRASE

    return Settings(
        mode=requested_mode,
        live_allowed=live_allowed,
        symbols=_parse_symbols(_get("SYMBOLS", "SPY,QQQ")),
        market_timezone=_get("MARKET_TIMEZONE", "America/Chicago"),
        trade_window_start=_parse_time(_get("TRADE_WINDOW_START", "09:00"), time(9, 0)),
        trade_window_end=_parse_time(_get("TRADE_WINDOW_END", "11:00"), time(11, 0)),
        loop_interval_seconds=_get_int("LOOP_INTERVAL_SECONDS", 60),
        alpaca_api_key=_get("ALPACA_API_KEY", ""),
        alpaca_secret_key=_get("ALPACA_SECRET_KEY", ""),
        alpaca_base_url=_get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        news_api_key=_get("NEWS_API_KEY", ""),
        risk=RiskConfig(
            starting_cash=_get_float("STARTING_CASH", 30_000.0),
            max_position_pct=_get_float("MAX_POSITION_PCT", 0.20),
            max_total_exposure_pct=_get_float("MAX_TOTAL_EXPOSURE_PCT", 1.0),
            max_daily_loss_pct=_get_float("MAX_DAILY_LOSS_PCT", 0.03),
            stop_loss_pct=_get_float("STOP_LOSS_PCT", 0.02),
            take_profit_pct=_get_float("TAKE_PROFIT_PCT", 0.04),
            max_open_positions=_get_int("MAX_OPEN_POSITIONS", 4),
        ),
        strategy=StrategyConfig(
            momentum_lookback=_get_int("MOMENTUM_LOOKBACK", 10),
            momentum_threshold=_get_float("MOMENTUM_THRESHOLD", 0.001),
        ),
    )
