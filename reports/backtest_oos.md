# Backtest: out-of-sample results

Data: warehouse `fct_prices_daily`, 2000-01-03 to 2026-11-18. In-sample < 2015-01-01, out-of-sample >= 2015-01-01. Costs 5 bps one-way turnover. Risk-free assumed 0.

## FX time-series momentum (6 pairs, long/short vs USD)

In-sample lookback grid (chosen by IS Sharpe, then frozen):

| lookback (months) | IS Sharpe | IS CAGR |
|---|---|---|
| 3 | 0.04 | -0.01% |
| 6 | -0.20 | -1.74% |
| 9 | 0.24 | 1.50% |
| 12 | -0.18 | -1.52% |

Chosen lookback: **9 months**

- Out-of-sample strategy: CAGR -1.21% | vol 5.08% | Sharpe -0.21 | max DD -17.94% | hit rate 46.2% | months 143 | avg monthly turnover 0.38
- Out-of-sample SPY buy-and-hold: CAGR 13.07% | vol 14.88% | Sharpe 0.90 | max DD -23.93% | hit rate 67.8% | months 143

Chart: `C:\Users\mcpag\market-warehouse\reports\equity\oos_fx.png`

## Sector momentum (top 3 of 9 SPDR sectors, long only)

In-sample lookback grid (chosen by IS Sharpe, then frozen):

| lookback (months) | IS Sharpe | IS CAGR |
|---|---|---|
| 3 | 0.51 | 6.43% |
| 6 | 0.51 | 6.40% |
| 9 | 0.49 | 6.34% |
| 12 | 0.51 | 6.58% |

Chosen lookback: **3 months**

- Out-of-sample strategy: CAGR 8.61% | vol 14.64% | Sharpe 0.64 | max DD -18.64% | hit rate 62.2% | months 143 | avg monthly turnover 0.77
- Out-of-sample SPY buy-and-hold: CAGR 13.07% | vol 14.88% | Sharpe 0.90 | max DD -23.93% | hit rate 67.8% | months 143

Chart: `C:\Users\mcpag\market-warehouse\reports\equity\oos_sector.png`

## LLM trading-agent signals

Not run. `signals/llm_decisions.csv` is empty, so there are no LLM decisions to test yet. See `signals/README.md` for how to generate them and why they need a point-in-time check.
