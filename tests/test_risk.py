from src.brokers.base import Account, OrderSide, Position
from src.risk.risk_manager import RiskManager
from src.strategies.base import Signal, SignalAction


def make_account(cash=30_000.0, positions=None):
    positions = positions or {}
    equity = cash + sum(p.market_value(p.avg_entry_price) for p in positions.values())
    return Account(cash=cash, equity=equity, positions=positions)


def test_position_size_respects_max_position_pct():
    rm = RiskManager(max_position_pct=0.20, max_open_positions=4)
    acct = make_account(cash=30_000.0)
    prices = {"SPY": 400.0}
    signals = [Signal("SPY", SignalAction.BUY, strength=1.0)]
    decisions = rm.size_orders(signals, acct, prices)
    assert len(decisions) == 1
    # 20% of 30k = 6000 -> 15 shares @ 400
    assert decisions[0].qty == 15
    assert decisions[0].side == OrderSide.BUY


def test_daily_loss_halt_blocks_new_entries():
    rm = RiskManager(max_daily_loss_pct=0.03)
    rm.start_day(30_000.0)
    # Down 4% -> should halt
    assert rm.update_and_check_halt(28_800.0) is True
    acct = make_account(cash=28_800.0)
    signals = [Signal("SPY", SignalAction.BUY, strength=1.0)]
    assert rm.size_orders(signals, acct, {"SPY": 400.0}) == []


def test_stop_loss_triggers_exit():
    rm = RiskManager(stop_loss_pct=0.02, take_profit_pct=0.04)
    pos = Position("SPY", qty=10, avg_entry_price=400.0)
    acct = make_account(cash=1000.0, positions={"SPY": pos})
    # Price down 3% -> stop loss should fire
    exits = rm.protective_exits(acct, {"SPY": 388.0})
    assert len(exits) == 1
    assert exits[0].side == OrderSide.SELL
    assert "stop-loss" in exits[0].reason


def test_take_profit_triggers_exit():
    rm = RiskManager(stop_loss_pct=0.02, take_profit_pct=0.04)
    pos = Position("SPY", qty=10, avg_entry_price=400.0)
    acct = make_account(cash=1000.0, positions={"SPY": pos})
    exits = rm.protective_exits(acct, {"SPY": 420.0})  # +5%
    assert len(exits) == 1
    assert "take-profit" in exits[0].reason


def test_max_open_positions_enforced():
    rm = RiskManager(max_position_pct=0.20, max_open_positions=1)
    acct = make_account(cash=30_000.0)
    prices = {"SPY": 400.0, "QQQ": 350.0}
    signals = [
        Signal("SPY", SignalAction.BUY, strength=1.0),
        Signal("QQQ", SignalAction.BUY, strength=1.0),
    ]
    decisions = rm.size_orders(signals, acct, prices)
    assert len(decisions) == 1  # only one new position allowed
