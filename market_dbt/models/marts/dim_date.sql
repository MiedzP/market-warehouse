with days as (
    select cast(d as date) as full_date
    from generate_series(date '2000-01-01', date '2030-12-31', interval 1 day) t(d)
)
select
    cast(strftime(full_date, '%Y%m%d') as integer) as date_key,
    full_date,
    year(full_date)                               as year_num,
    quarter(full_date)                            as quarter_num,
    month(full_date)                              as month_num,
    dayofweek(full_date)                          as day_of_week,
    dayofweek(full_date) in (0, 6)                as is_weekend
from days
