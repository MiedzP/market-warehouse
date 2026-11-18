with p as (
    select s.*, d.date_key, i.instrument_key
    from {{ ref('stg_prices') }} s
    join {{ ref('dim_date') }} d on d.full_date = s.trade_date
    join {{ ref('dim_instrument') }} i on i.symbol = s.symbol
)
select
    date_key,
    instrument_key,
    open_px, high_px, low_px, close_px, adj_close_px, volume,
    adj_close_px / lag(adj_close_px) over (partition by instrument_key order by date_key) - 1 as daily_return
from p
