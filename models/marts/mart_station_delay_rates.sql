-- One row per station + line (74 rows): how often delays happen there,
-- relative to how many people use that station on a typical weekday.
--
-- Choices (see docs/decisions.md):
--   * weekdays only, because the ridership figure is a typical weekday
--   * "A TO B" rows count toward the first station named (decision #12)
--   * delays are summarised to station + line FIRST, then joined to ridership
--     (one row per incident vs one number per station: different grains)
--   * start from the station list so stations with zero delays still appear

with weekday_delays as (
    select *
    from {{ ref('fct_subway_delays') }}
    where day_of_week not in ('Saturday', 'Sunday')
),

period as (
    -- every weekday in the data range has at least one delay somewhere,
    -- so this is the number of weekdays covered
    select count(distinct delay_date) as weekdays_in_period
    from weekday_delays
),

by_station as (
    select
        station_name,
        station_line                                  as line,
        count(*)                                      as incidents,
        count(*) filter (where min_delay > 0)         as delay_incidents,
        sum(min_delay)                                as minutes_lost
    from weekday_delays
    where station_name is not null
      and station_line is not null
    --   and station_mapping_type <> 'BETWEEN'
    group by 1, 2
)

select
    s.station_name,
    s.line,
    s.line_number,
    r.weekday_station_usage,
    p.weekdays_in_period,

    coalesce(b.incidents, 0)                          as incidents,
    coalesce(b.delay_incidents, 0)                    as delay_incidents,
    coalesce(b.minutes_lost, 0)                       as minutes_lost,

    round(coalesce(b.delay_incidents, 0) / p.weekdays_in_period, 3)
                                                      as delay_incidents_per_weekday,
    round(coalesce(b.minutes_lost, 0) / p.weekdays_in_period, 2)
                                                      as minutes_lost_per_weekday,

    -- the headline numbers: per 100,000 station users (entries + exits)
    round(coalesce(b.delay_incidents, 0) / p.weekdays_in_period
          / r.weekday_station_usage * 100000, 2)      as delay_incidents_per_100k_users,
    round(coalesce(b.minutes_lost, 0) / p.weekdays_in_period
          / r.weekday_station_usage * 100000, 1)      as minutes_lost_per_100k_users

from {{ ref('stations') }} as s
join {{ ref('station_ridership') }} as r
    using (station_name, line)
cross join period as p
left join by_station as b
    using (station_name, line)
