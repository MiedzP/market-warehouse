"""Dagster assets: raw ingestion -> dbt build (star schema) -> backtest outputs."""
import pathlib
import shutil
import subprocess
import sys

from dagster import AssetExecutionContext, Definitions, ScheduleDefinition, asset, define_asset_job

from .ingest import ROOT, fetch_all_fred, fetch_prices, load_raw

DBT_DIR = ROOT / "market_dbt"


def _dbt_exe():
    """Find the dbt executable: PATH first, then the user Scripts folder pip installs into."""
    found = shutil.which("dbt")
    if found:
        return found
    user_scripts = pathlib.Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts" / "dbt.exe"
    return str(user_scripts)


@asset(group_name="raw", description="Daily OHLCV for ETFs, FX pairs and VIX from Yahoo Finance via yfinance.")
def raw_prices():
    return fetch_prices()


@asset(group_name="raw", description="Selected FRED macro series (CSV endpoint, no key).")
def raw_fred_series():
    return fetch_all_fred()


@asset(group_name="raw", deps=[raw_prices, raw_fred_series],
       description="Full refresh of DuckDB schema raw from the two raw assets.")
def warehouse_raw_tables(raw_prices, raw_fred_series):
    return load_raw(raw_prices, raw_fred_series)


@asset(group_name="warehouse", deps=[warehouse_raw_tables],
       description="dbt build: staging views, star-schema dimensions and facts, and dbt tests.")
def dbt_star_schema(context: AssetExecutionContext):
    res = subprocess.run([_dbt_exe(), "build", "--profiles-dir", str(DBT_DIR), "--project-dir", str(DBT_DIR)],
                         capture_output=True, text=True, cwd=str(DBT_DIR))
    context.log.info(res.stdout[-4000:])
    if res.returncode != 0:
        raise RuntimeError(res.stdout[-4000:] + res.stderr[-2000:])
    return "ok"


daily_job = define_asset_job("daily_market_refresh", selection=[raw_prices, raw_fred_series,
                                                                warehouse_raw_tables, dbt_star_schema])
daily_schedule = ScheduleDefinition(job=daily_job, cron_schedule="0 18 * * 1-5",
                                    execution_timezone="America/New_York")

defs = Definitions(
    assets=[raw_prices, raw_fred_series, warehouse_raw_tables, dbt_star_schema],
    jobs=[daily_job],
    schedules=[daily_schedule],
)
