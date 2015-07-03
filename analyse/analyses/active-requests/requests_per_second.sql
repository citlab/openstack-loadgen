
create table if not exists analyse_requests_per_second as
select second, count(*) from active_requests as data group by second;

