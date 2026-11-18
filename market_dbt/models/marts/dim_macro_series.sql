select
    row_number() over (order by series_id) as series_key,
    series_id,
    case series_id
        when 'DGS2' then 'US 2-year Treasury yield'
        when 'DGS10' then 'US 10-year Treasury yield'
        when 'FEDFUNDS' then 'Effective federal funds rate'
        when 'CPIAUCSL' then 'CPI, all urban consumers'
        when 'UNRATE' then 'Unemployment rate'
        when 'DTWEXBGS' then 'Broad trade-weighted USD index'
    end as series_name,
    case series_id
        when 'FEDFUNDS' then 'monthly'
        when 'CPIAUCSL' then 'monthly'
        when 'UNRATE' then 'monthly'
        else 'daily'
    end as frequency
from (select distinct series_id from {{ ref('stg_fred_series') }})
