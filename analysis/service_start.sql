
-- Sunday 8am (first hour of Sunday service): which causes lead?
select
    delay_code,
    delay_description,
    count(*) as num_incidents
from ttc.main.fct_subway_delays
where day_of_week = 'Sunday'
  and hour(delay_ts) = 8
  and min_delay != 0
group by delay_code, delay_description
order by num_incidents desc;



--delays on non Sunday mornings - also due to service/maintenance work/issues

select 
--day_of_week,delay_ts,
count(*) as Num_Incidents,delay_code,delay_description from ttc.main.fct_subway_delays
where 1=1
and hour(delay_ts) >= 5
and hour(delay_ts) < 6
and day_of_week != 'Sunday'
and min_delay != 0
group by delay_code,delay_description
order by count(*) desc;