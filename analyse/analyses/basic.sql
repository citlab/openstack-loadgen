
create table if not exists seconds as
    select cast(start as integer) as second from SOURCETABLE group by cast(start as integer);

create table if not exists minsecond as
    select min(second) as second from seconds;

update seconds
    set second = second-(select min(second) from minsecond)
    where second >= (select min(second) from minsecond);

create table if not exists all_requests as
select
    cast(start as integer)-(select min(second) from minsecond) as second,
    start-(select min(second) from minsecond) as start,
    start+request_time-(select min(second) from minsecond) as end,
    request_time as time,
    error
from SOURCETABLE;

create table if not exists requests as
select second, start, end, time
    from all_requests
    where error is null;

create table if not exists errors as
select * from all_requests
    where error is not null;

create table if not exists active_requests as
select
    A.second, B.start, B.end, B.time
from
    seconds A join requests B
    on B.start < A.second+1 and B.end > A.second;

create table if not exists active_requests_minutes as
select cast(second/60 as integer) as minute, start, end, time from active_requests
group by cast(second/60 as integer), start, end, time;

