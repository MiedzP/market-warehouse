"""Monthly backtests on the warehouse marts, with an in-sample / out-of-sample split.

Protocol
- Signals use only data up to the month-end they are computed on; positions earn the NEXT month's return.
- Costs: 5 bps per unit of one-way turnover.
- Lookback is chosen on IN-SAMPLE (2000-2014) Sharpe, then frozen and run once on OUT-OF-SAMPLE (2015-2026).
- Sharpe uses risk-free = 0 (simplification; say so in any write-up).
"""
import pathlib
import sys

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse" / "market.duckdb"
OUT = ROOT / "reports"
SPLIT = pd.Timestamp("2015-01-01")
COST_BPS = 5
LOOKBACKS = [3, 6, 9, 12]  # months

FX_PAIRS = {  # yfinance quote -> sign converting pair move to currency-vs-USD move
    "EURUSD=X": 1, "GBPUSD=X": 1, "AUDUSD=X": 1,   # USD per foreign ccy
    "JPY=X": -1, "CAD=X": -1, "CHF=X": -1,         # foreign ccy per USD
}
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
SECTOR_TOP_N = 3


def load_prices():
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    df = con.execute("""
        select d.full_date as dt, i.symbol, f.adj_close_px as px
        from main_marts.fct_prices_daily f
        join main_marts.dim_date d on d.date_key = f.date_key
        join main_marts.dim_instrument i on i.instrument_key = f.instrument_key
    """).df()
    con.close()
    px = df.pivot(index="dt", columns="symbol", values="px").sort_index()
    px.index = pd.to_datetime(px.index)
    return px


def month_end(px):
    return px.resample("ME").last()  # last available close of each month


def metrics(ret, turnover=None):
    ret = ret.dropna()
    years = len(ret) / 12
    equity = (1 + ret).cumprod()
    cagr = equity.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = ret.std() * np.sqrt(12)
    sharpe = ret.mean() * 12 / vol if vol > 0 else np.nan
    dd = (equity / equity.cummax() - 1).min()
    out = {"CAGR": cagr, "Vol": vol, "Sharpe": sharpe, "MaxDD": dd, "Months": len(ret),
           "HitRate": (ret > 0).mean()}
    if turnover is not None:
        out["AvgTurnover"] = turnover.reindex(ret.index).mean()
    return out


def apply_costs(weights, asset_ret):
    """weights[t] are set at month-end t and earn asset_ret[t+1]. Costs charged when weights change."""
    w = weights.fillna(0.0)
    gross = (w * asset_ret.shift(-1).reindex(w.index).fillna(0.0)).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(w.abs().sum(axis=1))
    net = gross - turnover * COST_BPS / 10000
    return net.dropna(), turnover


# ---------- Strategy 1: FX time-series momentum ----------
def fx_momentum_weights(me, lookback):
    cols = list(FX_PAIRS)
    ccy_px = me[cols].copy()
    for c, s in FX_PAIRS.items():
        ccy_px[c] = ccy_px[c] ** s  # convert to currency-vs-USD level so 'up' always means currency strengthened
    score = ccy_px.shift(1) / ccy_px.shift(1 + lookback) - 1  # skip the most recent month
    w = np.sign(score) / score.notna().sum(axis=1).replace(0, np.nan).values[:, None]
    return w, ccy_px.pct_change()


# ---------- Strategy 2: sector momentum (top-N, long only) ----------
def sector_momentum_weights(me, lookback):
    px = me[SECTORS]
    score = px.shift(1) / px.shift(1 + lookback) - 1
    rank = score.rank(axis=1, ascending=False)
    top = (rank <= SECTOR_TOP_N).astype(float)
    return top.div(top.sum(axis=1).replace(0, np.nan), axis=0), px.pct_change()


def run_grid(name, builder, me):
    rows, results = [], {}
    for lb in LOOKBACKS:
        w, r = builder(me, lb)
        net, to = apply_costs(w, r)
        ins = net[net.index < SPLIT]
        oos = net[net.index >= SPLIT]
        rows.append({"strategy": name, "lookback_m": lb,
                     "IS_Sharpe": metrics(ins)["Sharpe"], "IS_CAGR": metrics(ins)["CAGR"]})
        results[lb] = (net, to)
    grid = pd.DataFrame(rows)
    best = int(grid.loc[grid["IS_Sharpe"].idxmax(), "lookback_m"])  # chosen in-sample
    net, to = results[best]
    oos_net = net[net.index >= SPLIT]
    return grid, best, oos_net, to[to.index >= SPLIT], net


def fmt(m):
    return (f"CAGR {m['CAGR']:.2%} | vol {m['Vol']:.2%} | Sharpe {m['Sharpe']:.2f} | "
            f"max DD {m['MaxDD']:.2%} | hit rate {m['HitRate']:.1%} | months {m['Months']}")


def main():
    px = load_prices()
    me = month_end(px)
    bench_ret = me["SPY"].pct_change().dropna()
    bench_oos = bench_ret[bench_ret.index >= SPLIT]
    lines = ["# Backtest: out-of-sample results", "",
             f"Data: warehouse `fct_prices_daily`, {px.index.min().date()} to {px.index.max().date()}. "
             f"In-sample < {SPLIT.date()}, out-of-sample >= {SPLIT.date()}. "
             f"Costs {COST_BPS} bps one-way turnover. Risk-free assumed 0.", ""]

    strategies = [("FX time-series momentum (6 pairs, long/short vs USD)", fx_momentum_weights),
                  (f"Sector momentum (top {SECTOR_TOP_N} of {len(SECTORS)} SPDR sectors, long only)", sector_momentum_weights)]

    summary_rows = []
    for name, builder in strategies:
        grid, best, oos, oos_to, _ = run_grid(name, builder, me)
        lines += [f"## {name}", "", "In-sample lookback grid (chosen by IS Sharpe, then frozen):", "",
                  "| lookback (months) | IS Sharpe | IS CAGR |", "|---|---|---|"]
        for _, r in grid.iterrows():
            lines.append(f"| {int(r.lookback_m)} | {r.IS_Sharpe:.2f} | {r.IS_CAGR:.2%} |")
        m = metrics(oos, oos_to)
        b = metrics(bench_oos)
        lines += ["", f"Chosen lookback: **{best} months**", "",
                  f"- Out-of-sample strategy: {fmt(m)} | avg monthly turnover {m['AvgTurnover']:.2f}",
                  f"- Out-of-sample SPY buy-and-hold: {fmt(b)}", ""]
        summary_rows.append((name, m, b))
        series = oos
        (OUT / "equity").mkdir(parents=True, exist_ok=True)
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(9, 4.5))
            (1 + series).cumprod().plot(ax=ax, label=f"{name} ({best}m)")
            (1 + bench_oos).cumprod().plot(ax=ax, label="SPY buy-and-hold")
            ax.set_title("Out-of-sample growth of 1 (after costs)")
            ax.legend(fontsize=8)
            fname = OUT / "equity" / f"oos_{name.split()[0].lower()}.png"
            fig.tight_layout(); fig.savefig(fname, dpi=110); plt.close(fig)
            lines.append(f"Chart: `{fname}`")
            lines.append("")
        except Exception as e:
            lines.append(f"(chart skipped: {e})")

    # LLM strategy hook: reads decisions produced by the TradingAgents runs
    llm_file = ROOT / "signals" / "llm_decisions.csv"
    lines += ["## LLM trading-agent signals", ""]
    if llm_file.exists() and llm_file.stat().st_size > 0:
        from backtest.llm_strategy import run as run_llm
        m, n = run_llm(me, llm_file)
        lines.append(f"{n} decisions loaded. Out-of-sample: {fmt(m)} | avg turnover {m['AvgTurnover']:.2f}")
    else:
        lines.append("Not run. `signals/llm_decisions.csv` is empty, so there are no LLM decisions to test yet. "
                     "See `signals/README.md` for how to generate them and why they need a point-in-time check.")
    lines.append("")

    out = OUT / "backtest_oos.md"
    OUT.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    sys.exit(main())
