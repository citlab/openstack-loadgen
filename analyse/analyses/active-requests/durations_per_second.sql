
create table if not exists analyse_durations_per_second as
select second, avg(time) as data from active_requests group by second;

