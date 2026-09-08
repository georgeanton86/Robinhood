#!/usr/bin/env python3
"""CLI entry point.

Examples:
    python run.py backtest --strategy momentum --symbols SPY QQQ
    python run.py paper --broker sim --strategy momentum --cycles 5
    python run.py paper --broker alpaca --strategy momentum_sentiment
"""
from __future__ import annotations

import argparse
import sys
import time

from config import load_settings
from src.utils import setup_logging


def _build_strategy(name: str, settings):
    from src.strategies import STRATEGIES

    if name not in STRATEGIES:
        raise SystemExit(f"Unknown strategy '{name}'. Choose from: {', '.join(STRATEGIES)}")
    cls = STRATEGIES[name]
    return cls(
        lookback=settings.strategy.momentum_lookback,
        threshold=settings.strategy.momentum_threshold,
    )


def _build_risk(settings):
    from src.risk import RiskManager

    r = settings.risk
    return RiskManager(
        max_position_pct=r.max_position_pct,
        max_total_exposure_pct=r.max_total_exposure_pct,
        max_daily_loss_pct=r.max_daily_loss_pct,
        stop_loss_pct=r.stop_loss_pct,
        take_profit_pct=r.take_profit_pct,
        max_open_positions=r.max_open_positions,
    )


def cmd_backtest(args, settings):
    from backtest import run_backtest
    from src.data.market_data import get_provider

    symbols = [s.upper() for s in (args.symbols or settings.symbols)]
    strategy = _build_strategy(args.strategy, settings)
    data = get_provider("synthetic")
    result = run_backtest(
        strategy,
        symbols,
        data=data,
        starting_cash=settings.risk.starting_cash,
        risk=_build_risk(settings),
    )
    print(f"\n=== Backtest: {args.strategy} on {', '.join(symbols)} (synthetic data) ===")
    print(result.summary())
    print(
        "\nNote: synthetic data. Swap in real bars (yfinance/Alpaca) and remember a "
        "good backtest is a reason to PAPER-test, not to go live.\n"
    )


def cmd_paper(args, settings):
    from src.data.market_data import get_provider
    from src.data.sentiment import get_sentiment_provider
    from src.engine import TradingEngine

    symbols = [s.upper() for s in (args.symbols or settings.symbols)]
    strategy = _build_strategy(args.strategy, settings)
    risk = _build_risk(settings)

    # --- pick broker ------------------------------------------------------
    if args.broker == "sim":
        from src.brokers.sim import SimBroker

        broker = SimBroker(starting_cash=settings.risk.starting_cash)
        data = get_provider("synthetic")
    elif args.broker == "alpaca":
        from src.brokers.alpaca import AlpacaBroker

        # PAPER unless the operator explicitly opted in to live.
        paper = not settings.is_live
        broker = AlpacaBroker(settings.alpaca_api_key, settings.alpaca_secret_key, paper=paper)
        try:
            data = get_provider("yfinance")
        except ImportError:
            print("yfinance not installed; falling back to synthetic prices.", file=sys.stderr)
            data = get_provider("synthetic")
    else:
        raise SystemExit(f"Unknown broker '{args.broker}'")

    sentiment = get_sentiment_provider("neutral")

    engine = TradingEngine(
        broker=broker,
        data=data,
        strategy=strategy,
        risk=risk,
        symbols=symbols,
        sentiment=sentiment,
        allow_live=settings.is_live,
        market_timezone=settings.market_timezone,
        window_start=settings.trade_window_start,
        window_end=settings.trade_window_end,
    )

    mode = "LIVE" if settings.is_live else "PAPER"
    print(f"[{mode}] Running {args.strategy} on {', '.join(symbols)} via {args.broker} broker.")
    if settings.is_live:
        print("!!! LIVE TRADING WITH REAL MONEY IS ENABLED. Ctrl-C to stop. !!!")

    cycle = 0
    try:
        while True:
            cycle += 1
            orders = engine.run_cycle()
            acct = broker.get_account()
            print(f"cycle {cycle}: equity=${acct.equity:,.2f} cash=${acct.cash:,.2f} "
                  f"positions={len(broker.get_positions())} orders_this_cycle={len(orders)}")
            if args.cycles and cycle >= args.cycles:
                break
            time.sleep(settings.loop_interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped by user.")


def main(argv=None):
    settings = load_settings()
    setup_logging()

    parser = argparse.ArgumentParser(description="Paper-first automated trading agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bt = sub.add_parser("backtest", help="Backtest a strategy on historical/synthetic data")
    p_bt.add_argument("--strategy", default="momentum")
    p_bt.add_argument("--symbols", nargs="*", default=None)

    p_pp = sub.add_parser("paper", help="Run the live loop (paper by default)")
    p_pp.add_argument("--broker", default="sim", choices=["sim", "alpaca"])
    p_pp.add_argument("--strategy", default="momentum")
    p_pp.add_argument("--symbols", nargs="*", default=None)
    p_pp.add_argument("--cycles", type=int, default=0, help="0 = run forever")

    args = parser.parse_args(argv)

    if settings.mode == "live" and not settings.live_allowed:
        print("TRADING_MODE=live but ALLOW_LIVE_TRADING opt-in is missing — "
              "running in PAPER mode for safety.", file=sys.stderr)

    if args.command == "backtest":
        cmd_backtest(args, settings)
    elif args.command == "paper":
        cmd_paper(args, settings)


if __name__ == "__main__":
    main()
