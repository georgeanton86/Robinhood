"""Test the "trailing stop + buy back in" idea honestly.

Runs your strategy (let a winner run, lock in part of the gain with a trailing
stop, then re-enter when it climbs again) against simply buying and holding, on
several Doge-like volatile scenarios. Same data for both, no cherry-picking.
"""
from __future__ import annotations

from backtest import run_backtest
from src.data.market_data import SyntheticData
from src.risk.risk_manager import RiskManager
from src.strategies.momentum import MomentumStrategy

CASH = 100.0  # use $100 so the numbers are readable; it scales to any size


def buy_and_hold(series, cash):
    closes = series["close"]
    return cash / float(closes.iloc[0]) * float(closes.iloc[-1])


def trailing_risk():
    return RiskManager(
        max_position_pct=1.0, max_open_positions=1, allow_fractional=True,
        trailing_stop_pct=0.03,   # give back at most ~3% from the peak
        stop_loss_pct=0.03,       # and cap a loss that never became a gain
        take_profit_pct=9.99,     # disabled, so winners are free to run
        max_daily_loss_pct=1.0,   # don't halt during the test
    )


SCENARIOS = [
    ("Choppy / sideways (the whipsaw trap)", 0.0000, 0.020, 11),
    ("Steady uptrend",                        0.0015, 0.015, 22),
    ("Crash / downtrend",                    -0.0015, 0.020, 33),
    ("Calm drift up",                         0.0004, 0.008, 44),
]


def main():
    print("=" * 74)
    print(f"  YOUR IDEA (trailing stop + re-enter) vs. just BUY & HOLD  — start ${CASH:.0f}")
    print("=" * 74)
    print(f"\n{'scenario':<38}{'buy&hold':>11}{'your bot':>11}{'trades':>8}")
    print("-" * 74)

    for name, drift, vol, seed in SCENARIOS:
        src = SyntheticData(seed=seed, start_price=0.20, drift=drift, vol=vol, n=260)
        series = src.full_series("DOGE")

        bh_end = buy_and_hold(series, CASH)
        result = run_backtest(
            MomentumStrategy(lookback=10, threshold=0.001),
            ["DOGE"], data=src, starting_cash=CASH, risk=trailing_risk(), warmup=12,
        )
        bot_end = result.ending_equity

        print(f"{name:<38}{bh_end:>10.2f}{bot_end:>11.2f}{result.num_trades:>8}")

    print("-" * 74)
    print("\nRead the columns: when 'your bot' beats 'buy&hold', the trailing idea won.")
    print("Watch the choppy row especially — that's where 'sell the dip, buy the")
    print("bounce' gets chopped up by many small losses (whipsaw), even though every")
    print("single rule sounded smart.")


if __name__ == "__main__":
    main()
