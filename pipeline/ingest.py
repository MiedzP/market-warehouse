"""Raw ingestion: yfinance (prices) and FRED CSV (macro). Writes to DuckDB schema `raw`."""
import datetime as dt
import io
import pathlib

import duckdb
import pandas as pd
import requests
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "warehouse" / "market.duckdb"

START = "2000-01-01"

# ticker -> (asset_class, description)
INSTRUMENTS = {
    "SPY": ("equity", "S&P 500 ETF"),
    "QQQ": ("equity", "Nasdaq-100 ETF"),
    "IWM": ("equity", "Russell 2000 ETF"),
    "XLB": ("equity", "Materials sector"),
    "XLE": ("equity", "Energy sector"),
    "XLF": ("equity", "Financials sector"),
    "XLI": ("equity", "Industrials sector"),
    "XLK": ("equity", "Technology sector"),
    "XLP": ("equity", "Consumer staples sector"),
    "XLU": ("equity", "Utilities sector"),
    "XLV": ("equity", "Health care sector"),
    "XLY": ("equity", "Consumer discretionary sector"),
    "TLT": ("bond", "20+ year Treasury ETF"),
    "GLD": ("commodity", "Gold ETF"),
    "EURUSD=X": ("fx", "USD per EUR"),
    "GBPUSD=X": ("fx", "USD per GBP"),
    "AUDUSD=X": ("fx", "USD per AUD"),
    "JPY=X": ("fx", "JPY per USD"),
    "CAD=X": ("fx", "CAD per USD"),
    "CHF=X": ("fx", "CHF per USD"),
    "^VIX": ("volatility", "CBOE Volatility Index"),
}

# FRED series id -> (description, frequency)
FRED_SERIES = {
    "DGS2": ("2-year Treasury yield, %", "daily"),
    "DGS10": ("10-year Treasury yield, %", "daily"),
    "FEDFUNDS": ("Effective federal funds rate, %", "monthly"),
    "CPIAUCSL": ("CPI, all urban consumers, index", "monthly"),
    "UNRATE": ("Unemployment rate, %", "monthly"),
    "DTWEXBGS": ("Trade-weighted US dollar index, broad", "daily"),
}


def fetch_prices(start=START, end=None):
    """Long-format daily OHLCV for every instrument in INSTRUMENTS."""
    tickers = list(INSTRUMENTS)
    raw = yf.download(tickers, start=start, end=end, auto_adjust=False,
                      progress=False, threads=True, group_by="column")
    long = raw.stack(level=1, future_stack=True).reset_index()
    long.columns = [str(c).lower().replace(" ", "_") for c in long.columns]
    long = long.rename(columns={"date": "trade_date", "ticker": "symbol"})
    keep = ["trade_date", "symbol", "open", "high", "low", "close", "adj_close", "volume"]
    long = long[keep].dropna(subset=["close"])
    long["trade_date"] = pd.to_datetime(long["trade_date"]).dt.date
    long["ingested_at"] = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return long.sort_values(["symbol", "trade_date"]).reset_index(drop=True)


def fetch_fred(series_id, start=START):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, timeout=60, headers={"User-Agent": "market-warehouse/0.1"})
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["observation_date", "value"]
    df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED uses "." for missing
    df = df[df["observation_date"] >= pd.Timestamp(start).date()].dropna(subset=["value"])
    df.insert(0, "series_id", series_id)
    df["ingested_at"] = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return df


def fetch_all_fred(start=START):
    return pd.concat([fetch_fred(s, start) for s in FRED_SERIES], ignore_index=True)


def load_raw(prices, macro, db_path=WAREHOUSE):
    """Full refresh of raw tables. Small enough to rebuild daily; keeps the job idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.register("p", prices)
    con.execute("CREATE OR REPLACE TABLE raw.prices AS SELECT * FROM p")
    con.register("m", macro)
    con.execute("CREATE OR REPLACE TABLE raw.fred_series AS SELECT * FROM m")
    counts = {
        "raw.prices": con.execute("SELECT count(*) FROM raw.prices").fetchone()[0],
        "raw.fred_series": con.execute("SELECT count(*) FROM raw.fred_series").fetchone()[0],
    }
    con.close()
    return counts
