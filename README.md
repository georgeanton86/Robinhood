# Trading Agent (paper-first)

A multi-strategy automated trading agent, built to run **safely in paper
(simulated) mode first**. It replicates the common "momentum" and
"momentum + sentiment" agent designs — trading index ETFs (SPY/QQQ) in the
morning window, plus a tech-stock momentum/sentiment agent — but wires them to
a broker built for automation (**Alpaca**) instead of a reverse-engineered
Robinhood connection, and gates real-money trading behind explicit, deliberate
safeguards.

> ⚠️ **Read this first — this is not financial advice.**
>
> - Automated trading is **high risk**. The large majority of retail algo
>   traders **underperform a simple index fund, and many lose money.** No
>   strategy here is guaranteed — or even likely — to beat the market.
> - **Money you need soon should not be here.** Funds you'll need within a few
>   years (e.g. near-term retirement money) belong in stable, diversified,
>   low-cost investments — not an automated trading bot. For a decision that
>   size, talk to a **fee-only fiduciary financial advisor**.
> - This project **defaults to paper trading** (fake money). Live trading is
>   off unless you deliberately, explicitly enable it. Please prove a strategy
>   out in paper for a long time before you ever consider risking a real dollar.
> - **Robinhood has no official stock API**, and its Customer Agreement
>   prohibits automated trading. Using reverse-engineered libraries risks your
>   account (and the money in it) being frozen. That's why this uses Alpaca.

## What's inside

```
src/
  brokers/       Broker adapters behind one interface
    base.py        BrokerAdapter interface + Order/Position/Account types
    sim.py         SimBroker — pure in-memory simulation (no account, no risk)
    alpaca.py      AlpacaBroker — real Alpaca *paper* account (opt-in live)
  data/
    market_data.py Price bars: synthetic (offline), yfinance, or Alpaca
    sentiment.py   Pluggable news-sentiment scoring (offline stub by default)
  strategies/
    base.py        Strategy interface + Signal type
    momentum.py    Short-window momentum on SPY/QQQ (morning window)
    momentum_sentiment.py  Momentum gated by news sentiment (ETFs or tech)
  risk/
    risk_manager.py  Position sizing, max daily loss halt, stops, PAPER guard
  engine/
    trading_engine.py  Live/paper loop tying it all together
backtest.py        Event-driven backtest with equity curve + stats
run.py             CLI entry point (backtest or paper loop)
tests/             Offline tests (synthetic data — no network/keys needed)
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Backtest a strategy on synthetic data — no keys, no network needed:
python run.py backtest --strategy momentum --symbols SPY QQQ

# 2) Run tests:
pytest -q

# 3) Paper-run against the in-memory simulator (no account needed):
python run.py paper --broker sim --strategy momentum

# 4) Paper-run against a real Alpaca *paper* account (free keys, fake money):
#    Copy .env.example -> .env and fill in your Alpaca PAPER keys, then:
python run.py paper --broker alpaca --strategy momentum_sentiment
```

## Going live (please don't rush this)

Live trading with real money is disabled by default. To even attempt it you must
set **both** of these, on purpose:

```
TRADING_MODE=live
ALLOW_LIVE_TRADING=YES_I_UNDERSTAND_THE_RISKS
```

If either is missing, the engine refuses to place real-money orders and stays in
paper mode. Do not enable this until you have watched the strategy trade in paper
for months and understand exactly how it behaves in a down market.

## Configuration

All settings come from environment variables (see `.env.example`) with safe
defaults. Nothing secret is committed — `.env` is gitignored.
