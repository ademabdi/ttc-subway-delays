-- One row per delay record from the source, with real types and flags.
-- Rule for staging: rename, cast, standardise. Never drop rows here -
-- problems are flagged so you can decide later what to filter.

with src as (
    select * from {{ source('raw', 'subway_delays') }}
),

typed as (
    select
        -- _id is just the row number in this file version; it can change on the
        -- next refresh, so we keep it for tracing but never use it as a key.
        cast("_id" as integer)                                  as source_row_id,

        cast("Date" as date)                                    as delay_date,
        strptime("Date" || ' ' || "Time", '%Y-%m-%d %H:%M')     as delay_ts,

        -- Recompute the weekday from the date. The source "Day" column is wrong
        -- for 2026-04-26 (63 rows say Saturday, it was a Sunday).
        dayname(cast("Date" as date))                           as day_of_week,

        upper(trim("Station"))                                  as station_raw,  -- free text, cut at 22 chars
        upper(trim("Code"))                                     as delay_code,
        cast("Min Delay" as integer)                            as min_delay,
        cast("Min Gap" as integer)                              as min_gap,
        nullif(upper(trim("Bound")), '')                        as bound,

        upper(trim("Line"))                                     as line_raw,
        case upper(replace("Line", ' ', ''))
            when 'YU'  then 'YU'
            when 'YUS' then 'YU'
            when 'BD'  then 'BD'
            when 'SHP' then 'SHP'
            when 'SRT' then 'SRT'
            else case when "Line" is null then null else 'OTHER' end
        end                                                     as line,

        -- 0 (and one 999) mean "no train recorded", not a real train number
        case when "Vehicle" in ('0', '999') then null
             else cast("Vehicle" as integer) end                as vehicle_number
    from src
),

-- Translate the free-text station into a real station (see seeds/station_mapping.csv).
-- Which line? Interchanges like St. George serve two lines. Trust the record's own
-- Line column when it's a line that station actually serves; otherwise fall back to
-- the line implied by the raw name ("ST GEORGE BD STATION" -> BD).
mapped as (
    select
        t.*,
        m.station_name,
        coalesce(s.line, m.line)                                as station_line,
        coalesce(m.mapping_type, 'NOT_IN_MAPPING')              as station_mapping_type
    from typed as t
    left join {{ ref('station_mapping') }} as m
        on t.station_raw = m.raw_value
    left join {{ ref('stations') }} as s
        on s.station_name = m.station_name
       and s.line = t.line
)

select
    *,
    min_delay = 0 as is_zero_delay,

    -- Same values in every column except _id = probably a double-entered event.
    -- Flagged, not removed (it could also be two genuine identical events).
    count(*) over (
        partition by delay_ts, station_raw, delay_code, min_delay, min_gap,
                     bound, line_raw, vehicle_number
    ) > 1 as is_possible_duplicate
from mapped
