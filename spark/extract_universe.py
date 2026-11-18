"""Download daily adjusted prices for the S&P 500 universe to parquet, in chunks. Input for the Spark job.

Survivorship bias: the symbol list is today's constituents, so delisted or removed names are missing.
"""
import pathlib
import time

import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "warehouse" / "data" / "universe_prices.parquet"


def main(start="2000-01-01", chunk=50):
    syms = pd.read_csv(ROOT / "pipeline" / "sp500_symbols.csv")["Symbol"].str.replace(".", "-", regex=False).tolist()
    frames = []
    for i in range(0, len(syms), chunk):
        batch = syms[i:i + chunk]
        raw = yf.download(batch, start=start, auto_adjust=False, progress=False, threads=True, group_by="column")
        if raw.empty:
            continue
        long = raw.stack(level=1, future_stack=True).reset_index()
        long.columns = [str(c).lower().replace(" ", "_") for c in long.columns]
        long = long.rename(columns={"date": "trade_date", "ticker": "symbol"})
        frames.append(long[["trade_date", "symbol", "open", "high", "low", "close", "adj_close", "volume"]].dropna(subset=["adj_close"]))
        print(f"chunk {i // chunk + 1}: {len(batch)} symbols, {len(long)} raw rows", flush=True)
        time.sleep(1)
    df = pd.concat(frames, ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).astype("datetime64[us]")  # Spark cannot read ns timestamps
    df.to_parquet(OUT, index=False)
    print(f"wrote {OUT} rows={len(df)} symbols={df['symbol'].nunique()}", flush=True)


if __name__ == "__main__":
    main()
