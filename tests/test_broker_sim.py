import pytest

from src.brokers.base import OrderSide
from src.brokers.sim import SimBroker


def test_buy_and_sell_roundtrip():
    b = SimBroker(starting_cash=10_000.0)
    b.set_price("SPY", 400.0)
    order = b.submit_order("SPY", 10, OrderSide.BUY)
    assert order.status == "filled"
    acct = b.get_account()
    assert acct.cash == pytest.approx(10_000.0 - 4_000.0)
    assert acct.positions["SPY"].qty == 10

    b.set_price("SPY", 410.0)
    b.submit_order("SPY", 10, OrderSide.SELL)
    acct = b.get_account()
    assert "SPY" not in acct.positions
    # sold 10 @ 410 => cash back up with profit
    assert acct.cash == pytest.approx(10_000.0 - 4_000.0 + 4_100.0)


def test_cannot_overspend():
    b = SimBroker(starting_cash=100.0)
    b.set_price("SPY", 400.0)
    order = b.submit_order("SPY", 1, OrderSide.BUY)
    assert order.status == "rejected"
    assert b.get_account().cash == 100.0


def test_cannot_sell_more_than_held():
    b = SimBroker(starting_cash=10_000.0)
    b.set_price("SPY", 400.0)
    b.submit_order("SPY", 5, OrderSide.BUY)
    order = b.submit_order("SPY", 10, OrderSide.SELL)
    # only 5 held -> sells 5, no shorting
    assert order.qty == 5
    assert "SPY" not in b.get_account().positions


def test_equity_tracks_price():
    b = SimBroker(starting_cash=10_000.0)
    b.set_price("SPY", 400.0)
    b.submit_order("SPY", 10, OrderSide.BUY)
    b.set_price("SPY", 500.0)
    assert b.equity() == pytest.approx(10_000.0 - 4_000.0 + 5_000.0)
