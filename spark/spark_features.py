"""PySpark job: panel features and a cross-sectional momentum test on the S&P 500 price history.

Reads  warehouse/data/universe_prices.parquet   (from extract_universe.py)
Writes warehouse/data/features_monthly.parquet  (month-end features and forward returns)
       reports/momentum_decile_spread.csv       (top-minus-bottom decile spread by year)

Survivorship bias: symbols are today's S&P 500 members, so this overstates what an investor
could have bought in the past.
"""
import os
import pathlib

JDK_DEFAULT = r"C:\Program Files\Eclipse Adoptium\jdk-17.0.21.9-hotspot"
if not os.environ.get("JAVA_HOME") and pathlib.Path(JDK_DEFAULT).exists():
    os.environ["JAVA_HOME"] = JDK_DEFAULT

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "warehouse" / "data" / "universe_prices.parquet"
DST = ROOT / "warehouse" / "data" / "features_monthly.parquet"
SPREAD_OUT = ROOT / "reports" / "momentum_decile_spread.csv"


def main():
    spark = (SparkSession.builder.appName("sp500-momentum-features")
             .master("local[*]")
             .config("spark.sql.shuffle.partitions", "16")
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    px = spark.read.parquet(str(SRC))
    rows_in = px.count()
    sym_w = Window.partitionBy("symbol").orderBy("trade_date")

    daily = (px
             .withColumn("ret", F.col("adj_close") / F.lag("adj_close", 1).over(sym_w) - 1)
             .withColumn("vol_63d", F.stddev("ret").over(sym_w.rowsBetween(-62, 0)) * F.sqrt(F.lit(252.0)))
             .withColumn("mom_12_1", F.lag("adj_close", 21).over(sym_w) / F.lag("adj_close", 252).over(sym_w) - 1)
             .withColumn("dollar_vol", F.col("close") * F.col("volume"))
             .withColumn("ym", F.date_format("trade_date", "yyyy-MM")))

    # last trading day of each month per symbol = the month-end observation
    me_w = Window.partitionBy("symbol", "ym").orderBy(F.col("trade_date").desc())
    month_end = (daily.withColumn("rn", F.row_number().over(me_w)).filter("rn = 1").drop("rn"))

    m_w = Window.partitionBy("symbol").orderBy("trade_date")
    monthly = (month_end
               .withColumn("fwd_1m_ret", F.lead("adj_close", 1).over(m_w) / F.col("adj_close") - 1)
               .filter(F.col("mom_12_1").isNotNull() & F.col("fwd_1m_ret").isNotNull() & F.col("vol_63d").isNotNull()))

    xs_w = Window.partitionBy("trade_date")
    monthly = (monthly
               .withColumn("mom_pctile", F.percent_rank().over(xs_w.orderBy("mom_12_1")))
               .withColumn("mom_decile", F.least(F.floor(F.col("mom_pctile") * 10) + 1, F.lit(10))))

    features = monthly.select("trade_date", "ym", "symbol", "adj_close", "mom_12_1", "vol_63d",
                              "dollar_vol", "mom_pctile", "mom_decile", "fwd_1m_ret")
    # Windows has no Hadoop native IO here (no winutils), so Spark computes and pandas writes the small output.
    features.toPandas().to_parquet(DST, index=False)

    spread = (features.groupBy("trade_date", "mom_decile").agg(F.avg("fwd_1m_ret").alias("avg_fwd"))
              .groupBy("trade_date")
              .agg(F.max(F.when(F.col("mom_decile") == 10, F.col("avg_fwd"))).alias("top"),
                   F.max(F.when(F.col("mom_decile") == 1, F.col("avg_fwd"))).alias("bottom"))
              .withColumn("spread", F.col("top") - F.col("bottom"))
              .withColumn("year", F.year("trade_date")))
    by_year = (spread.groupBy("year")
               .agg(F.avg("spread").alias("avg_monthly_spread"), F.count("*").alias("months"))
               .orderBy("year"))
    pdf = by_year.toPandas()
    pdf.to_csv(SPREAD_OUT, index=False)

    print(f"input rows: {rows_in:,}")
    print(f"feature rows (month-end, with 12-1 momentum and forward return): {features.count():,}")
    print(f"overall mean top-minus-bottom decile spread per month: {spread.agg(F.avg('spread')).first()[0]:.4%}")
    print(f"saved: {DST}\nsaved: {SPREAD_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
