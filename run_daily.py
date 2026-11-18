"""Run the whole daily pipeline once, without the Dagster UI: python run_daily.py"""
from dagster import materialize

from pipeline.definitions import raw_fred_series, raw_prices, warehouse_raw_tables, dbt_star_schema

if __name__ == "__main__":
    result = materialize([raw_prices, raw_fred_series, warehouse_raw_tables, dbt_star_schema])
    print("SUCCESS" if result.success else "FAILED")
