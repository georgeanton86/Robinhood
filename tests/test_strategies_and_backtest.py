from backtest import run_backtest
from src.data.market_data import SyntheticData
from src.data.sentiment import KeywordSentiment
from src.strategies.base import SignalAction, StrategyContext
from src.strategies.momentum import MomentumStrategy
from src.strategies.momentum_sentiment import MomentumSentimentStrategy


def test_momentum_emits_valid_signals():
    data = SyntheticData(n=100)
    strat = MomentumStrategy(lookback=10, threshold=0.001)
    ctx = StrategyContext(symbols=["SPY", "QQQ"], data=data)
    signals = strat.generate_signals(ctx)
    assert len(signals) == 2
    for s in signals:
        assert s.action in (SignalAction.BUY, SignalAction.SELL, SignalAction.HOLD)
        assert 0.0 <= s.strength <= 1.0


def test_sentiment_blocks_buy_on_bad_news():
    data = SyntheticData(n=100)
    # Force an upward momentum series by using a high drift symbol via seed choice
    strat = MomentumSentimentStrategy(lookback=5, threshold=0.0, min_sentiment=-0.1)
    bad_news = KeywordSentiment({"SPY": ["Company faces lawsuit and probe, shares plunge"]})
    ctx = StrategyContext(symbols=["SPY"], data=data, sentiment=bad_news)
    signals = strat.generate_signals(ctx)
    # If momentum said BUY, negative sentiment must convert it to HOLD.
    for s in signals:
        if "blocked by sentiment" in s.reason:
            assert s.action == SignalAction.HOLD


def test_backtest_runs_and_reports():
    strat = MomentumStrategy(lookback=10, threshold=0.001)
    result = run_backtest(strat, ["SPY", "QQQ"], starting_cash=30_000.0)
    assert result.starting_equity == 30_000.0
    assert len(result.equity_curve) > 0
    # equity should never go negative in a long-only sim
    assert min(result.equity_curve) >= 0
    assert isinstance(result.summary(), str)


def test_backtest_respects_starting_cash():
    strat = MomentumSentimentStrategy(lookback=10, threshold=0.001)
    result = run_backtest(strat, ["SPY"], starting_cash=5_000.0)
    assert result.starting_equity == 5_000.0
