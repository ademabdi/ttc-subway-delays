
-- delays on Sunday morning - due to service/maintenace work/issues
select 
--day_of_week,delay_ts,
count(*) as Num_Incidents,delay_code,delay_description from ttc.main.fct_subway_delays
where 1=1
and hour(delay_ts) = 8
and day_of_week = 'Sunday'
and min_delay != 0
group by delay_code,delay_description
--,day_of_week,delay_ts
--order by dayofweek, time_hour
order by count(*) desc



--delays on non Sunday mornings - also due to service/maintenace work/issues

select 
--day_of_week,delay_ts,
count(*) as Num_Incidents,delay_code,delay_description from ttc.main.fct_subway_delays
where 1=1
and hour(delay_ts) >= 5
and hour(delay_ts) < 6
and day_of_week != 'Sunday'
--and day_of_week != 'Saturday'
and min_delay != 0
group by delay_code,delay_description
--,day_of_week,delay_ts
--order by dayofweek, time_hour
order by count(*) desc