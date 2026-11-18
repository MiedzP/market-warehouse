select
    cast(trade_date as date)        as trade_date,
    upper(symbol)                   as symbol,
    cast(open as double)            as open_px,
    cast(high as double)            as high_px,
    cast(low as double)             as low_px,
    cast(close as double)           as close_px,
    cast(adj_close as double)       as adj_close_px,
    cast(volume as bigint)          as volume,
    ingested_at
from {{ source('raw', 'prices') }}
