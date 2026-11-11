-- One row per delay event with its code description attached.
-- LEFT join on purpose: 11 codes used in the data are missing from the lookup.
-- An inner join would silently drop ~1,900 delays; a left join keeps them
-- with a null description.

select
    d.source_row_id,
    d.delay_ts,
    d.delay_date,
    d.day_of_week,
    d.station_raw,
    d.station_name,
    d.station_line,
    d.station_mapping_type,
    d.line,
    d.line_raw,
    d.bound,
    d.delay_code,
    c.delay_description,
    c.delay_code is not null as has_code_description,
    d.min_delay,
    d.min_gap,
    d.vehicle_number,
    d.is_zero_delay,
    d.is_possible_duplicate
from {{ ref('stg_subway_delays') }} as d
left join {{ ref('stg_delay_codes') }} as c
    on d.delay_code = c.delay_code
