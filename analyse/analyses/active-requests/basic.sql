
create table if not exists active_requests as
select
    A.second, B.start, B.end, B.time
from
    seconds A join requests B
    on B.start < A.second+1 and B.end > A.second;

create table if not exists active_requests_minutes as
select cast(second/60 as integer) as minute, start, end, time from active_requests
group by cast(second/60 as integer), start, end, time;

