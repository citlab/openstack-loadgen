
create table if not exists errors as
    select start, request_time, error from keystone where error is not null;

create table if not exists seconds as
    select cast(start as integer) as second from keystone group by cast(start as integer);

create table if not exists minsecond as
    select min(second) as second from seconds;

update seconds
    set second = second-(select min(second) from minsecond)
    where second >= (select min(second) from minsecond);

create table if not exists keystone2 as
select
    cast(start as integer)-(select min(second) from minsecond) as second,
    start-(select min(second) from minsecond) as start,
    start+request_time-(select min(second) from minsecond) as end,
    request_time as time
from keystone where error is null;

-- For every second, join in the requests that have been active within that second
create table if not exists active_requests as
select
    A.second, B.start, B.end, B.time
from
    seconds A join keystone2 B
    on B.start < A.second+1 and B.end > A.second;

create table if not exists analyse_active_requests_number as
select second, count(*) from active_requests as data group by second;

create table if not exists analyse_request_durations as
select second, avg(time) as data from active_requests group by second;
