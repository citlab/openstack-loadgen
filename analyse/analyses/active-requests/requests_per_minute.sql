
create table if not exists analyse_requests_per_minute as
select minute, count(*) from active_requests_minutes as data group by minute;

