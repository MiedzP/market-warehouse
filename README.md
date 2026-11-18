# market-warehouse

Daily market and macro pipeline into a DuckDB star schema, dbt models and tests, monthly
out-of-sample backtests, and a PySpark cross-sectional momentum job on S&P 500 price history.

    yfinance + FRED  ->  raw (DuckDB)  ->  dbt (staging, star schema, tests)  ->  backtests / analysis
                                     \->  PySpark on S&P 500 panel (2.96M rows)

## Run

| Task | Command |
|---|---|
| Daily pipeline once (ingest, load, dbt build) | `python run_daily.py` |
| Dagster UI and daily schedule (weekdays 18:00 New York) | `dagster dev -f pipeline/definitions.py` |
| Backtests (in-sample / out-of-sample) | `python backtest/backtest.py` |
| Refresh S&P 500 panel (about 5 min) | `python spark/extract_universe.py` |
| PySpark momentum job | `python spark/spark_features.py` |

The Spark job needs a Java 17 runtime. It defaults to `C:\Program Files\Eclipse Adoptium\jdk-17.0.21.9-hotspot`
if `JAVA_HOME` is unset. Spark writes its output through pandas, because Windows has no Hadoop IO here.

## Layout

- `pipeline/`: ingestion (`ingest.py`) and Dagster assets, schedule and job (`definitions.py`)
- `market_dbt/`: dbt project. Staging views; `dim_date`, `dim_instrument`, `dim_macro_series`; facts `fct_prices_daily`, `fct_macro_daily`; 12 data tests
- `backtest/`: pandas backtests (`backtest.py`) and the LLM strategy hook (`llm_strategy.py`)
- `spark/`: S&P 500 extraction and the PySpark feature and momentum job
- `reports/`: backtest write-up, decile spread by year, equity charts
- `signals/`: LLM decision file (empty for now; see `signals/README.md`)

## Results so far

See `reports/backtest_oos.md` for the full tables. Out-of-sample 2015-2026, after 5 bps costs:
- FX time-series momentum (6 pairs): about -1% CAGR. It does not beat zero.
- Sector momentum (top 3 of 9 SPDR sectors): about 8.6% CAGR, against 13.1% for SPY buy-and-hold.
- LLM signals: not run. The decision file is empty.

## Caveats

- **Survivorship bias.** The S&P 500 list reflects today's constituents, so the Spark results overstate what was historically investable.
- **Look-ahead.** Signals use month-end data only, and positions earn the next month's return. The LLM leg must also be point-in-time before its results mean anything.
- **Risk-free rate** is set to 0 in Sharpe ratios.
- **Scale.** The Spark job handles about 3M rows, which is small enough for pandas. Spark is used here to show the skill, not because the data needs it.
- **Not investment advice.** These are research and portfolio exercises.
