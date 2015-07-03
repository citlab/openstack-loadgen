
select
    seconds.second, avg(end - start) as duration
from
    seconds left outer join all_requests on seconds.second == all_requests.second
group by seconds.second

