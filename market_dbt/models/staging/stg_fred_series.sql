select
    cast(observation_date as date) as observation_date,
    series_id,
    cast(value as double)          as value,
    ingested_at
from {{ source('raw', 'fred_series') }}
