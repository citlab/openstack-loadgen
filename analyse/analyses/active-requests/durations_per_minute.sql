
create table if not exists analyse_durations_per_minute as
select minute, avg(time) from active_requests_minutes as data group by minute;

