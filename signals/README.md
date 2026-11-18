# LLM decision file

`llm_decisions.csv` holds one row per month-end decision per instrument:

    decision_date,symbol,signal,source
    2019-06-28,XLK,1,TradingAgents v0.7 / model name

- `signal`: -1 (short), 0 (flat), +1 (long). The backtest takes equal gross exposure across the symbols each month.
- Generate rows with the TradingAgents framework (C:\Users\mcpag\TauricResearch\TradingAgents) at each month-end.
- Point-in-time: a decision must only use data available on its `decision_date`. TradingAgents' v0.5 changelog
  says this is enforced for its data paths; verify before trusting any backtest that uses it.
- Cost: each decision run calls an LLM several times per ticker, so a 20-year monthly run is expensive.
  Start with a few tickers and a 2-3 year window before scaling up.
