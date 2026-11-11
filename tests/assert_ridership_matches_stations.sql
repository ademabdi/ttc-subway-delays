-- Every ridership row must match a station + line in the master list.
-- dbt's built-in relationships test checks one column; this checks the pair.
-- A row returned here = a name that didn't translate (test fails).
select r.station_name, r.line
from {{ ref('station_ridership') }} as r
left join {{ ref('stations') }} as s
    using (station_name, line)
where s.station_name is null
