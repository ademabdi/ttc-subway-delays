-- The rates mart must have exactly one row per station + line.
-- Duplicates here would mean a join fanned out somewhere upstream.
select station_name, line, count(*) as n
from {{ ref('mart_station_delay_rates') }}
group by 1, 2
having count(*) > 1
