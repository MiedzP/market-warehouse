"""LLM strategy leg: turns trading-agent decisions into monthly weights for the same backtest engine.

Input file: signals/llm_decisions.csv with columns
  decision_date  (month-end date the decision was made, YYYY-MM-DD)
  symbol         (must exist in dim_instrument)
  signal         (-1 short, 0 flat, +1 long)
  source         (free text, e.g. 'TradingAgents v0.7 / model name')
Only decisions dated on or before the month-end they apply to are used (no look-ahead).
"""
import numpy as np
import pandas as pd

from backtest.backtest import apply_costs, metrics, SPLIT


def load_decisions(path):
    d = pd.read_csv(path, parse_dates=["decision_date"])
    d["signal"] = d["signal"].astype(float).clip(-1, 1)
    return d


def llm_weights(me, decisions):
    sig = decisions.pivot_table(index="decision_date", columns="symbol", values="signal", aggfunc="last")
    sig = sig.reindex(me.index, method="ffill")  # hold the latest decision until a new one arrives
    sig = sig.reindex(columns=me.columns).fillna(0.0)
    gross = sig.abs().sum(axis=1).replace(0, np.nan)
    return sig.div(gross, axis=0).fillna(0.0), me.pct_change()


def run(me, path):
    d = load_decisions(path)
    w, r = llm_weights(me, d)
    net, to = apply_costs(w, r)
    oos = net[net.index >= SPLIT]
    return metrics(oos, to[to.index >= SPLIT]), len(d)
