
select
    cast(min(start) as integer), count(*) as count
from
    all_requests group by cast((start/2) as integer)

