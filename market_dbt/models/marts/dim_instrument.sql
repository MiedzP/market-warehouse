select
    row_number() over (order by symbol)            as instrument_key,
    symbol,
    asset_class,
    description
from {{ ref('instrument_catalog') }}
