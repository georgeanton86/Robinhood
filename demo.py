"""Zero-setup demo: replay the bot trading a pretend $10 account, step by step.

No account, no keys, no network, no real money. It replays simulated price data
through the SAME engine/risk/broker code the real thing uses, and prints each
decision as it happens — so you can watch the bot "think" and trade.
"""
from __future__ import annotations

from backtest import _WindowedData
from src.brokers.sim import SimBroker
from src.data.market_data import SyntheticData
from src.engine.trading_engine import TradingEngine
from src.risk.risk_manager import RiskManager
from src.strategies.momentum import MomentumStrategy

STARTING_CASH = 10.0
SYMBOL = "SPY"


def main():
    print("=" * 64)
    print(f"  PRACTICE MODE — pretend ${STARTING_CASH:.2f}, fake money, real code")
    print("=" * 64)

    data_src = SyntheticData(n=180, vol=0.006, drift=0.0003)
    series = {SYMBOL: data_src.full_series(SYMBOL)}
    windowed = _WindowedData(series)

    broker = SimBroker(starting_cash=STARTING_CASH)
    risk = RiskManager(
        max_position_pct=1.0,       # $10 account: allow the whole balance in one spot
        max_open_positions=1,
        allow_fractional=True,      # buy fractions of a share (a share of SPY is ~$500)
        min_order_notional=1.0,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_daily_loss_pct=0.20,
    )
    strat = MomentumStrategy(lookback=10, threshold=0.0008)
    engine = TradingEngine(broker, windowed, strat, risk, [SYMBOL],
                           window_start=None, window_end=None)

    print(f"\n{'time':>6}  {'price':>8}  action")
    print("-" * 40)

    trades = 0
    shown = 0
    for i in range(15, windowed.length):
        windowed.set_index(i)
        risk.start_day(broker.equity())  # keep the daily guard from tripping in demo
        orders = engine.run_cycle()
        for o in orders:
            if o.status != "filled":
                continue
            trades += 1
            if shown < 18:  # keep the log readable
                ts = windowed.timestamp().strftime("%H:%M")
                emoji = "🟢 BUY " if o.side.value == "buy" else "🔴 SELL"
                print(f"{ts:>6}  ${o.filled_price:>7.2f}  {emoji} {o.qty:.4f} shares  "
                      f"(equity now ${broker.equity():.2f})")
                shown += 1
            elif shown == 18:
                print("   ... (more trades happening, hidden to keep this short) ...")
                shown += 1

    end_equity = broker.equity()
    pnl = end_equity - STARTING_CASH
    print("-" * 40)
    print(f"\nStarted with : ${STARTING_CASH:.2f}")
    print(f"Ended with   : ${end_equity:.2f}")
    print(f"Profit/loss  : ${pnl:+.2f}  ({pnl / STARTING_CASH * 100:+.1f}%)")
    print(f"Total trades : {trades}")
    print("\nThis was fake data + fake money — just to show the machine works.")
    print("On real money it behaves the same way, for real dollars (or pennies).")


if __name__ == "__main__":
    main()
