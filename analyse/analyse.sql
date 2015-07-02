
create table if not exists errors as
    select start, request_time, error from SOURCETABLE where error is not null;

create table if not exists seconds as
    select cast(start as integer) as second from SOURCETABLE group by cast(start as integer);

create table if not exists minsecond as
    select min(second) as second from seconds;

update seconds
    set second = second-(select min(second) from minsecond)
    where second >= (select min(second) from minsecond);

create table if not exists SOURCETABLE_RICH as
select
    cast(start as integer)-(select min(second) from minsecond) as second,
    start-(select min(second) from minsecond) as start,
    start+request_time-(select min(second) from minsecond) as end,
    request_time as time
from SOURCETABLE where error is null;

-- For every second, join in the requests that have been active within that second
create table if not exists active_requests as
select
    A.second, B.start, B.end, B.time
from
    seconds A join SOURCETABLE_RICH B
    on B.start < A.second+1 and B.end > A.second;

create table if not exists analyse_active_requests_number as
select second, count(*) from active_requests as data group by second;

create table if not exists analyse_request_durations as
select second, avg(time) as data from active_requests group by second;

-- Analysis per minute, if runtime too long for second-wise analysis

create table if not exists active_requests_minutes as
select cast(second/60 as integer) as minute, start, end, time from active_requests
group by cast(second/60 as integer), start, end, time;

create table if not exists analyse_active_requests_number_per_minute as
select minute, count(*) from active_requests_minutes as data group by minute;

create table if not exists analyse_active_requests_durations_per_minute as
select minute, avg(time) from active_requests_minutes as data group by minute;

