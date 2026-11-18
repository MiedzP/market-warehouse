select
    cast(strftime(s.observation_date, '%Y%m%d') as integer) as date_key,
    m.series_key,
    s.value
from {{ ref('stg_fred_series') }} s
join {{ ref('dim_macro_series') }} m on m.series_id = s.series_id
