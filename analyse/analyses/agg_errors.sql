
select
    seconds.second as second, count(errors.error) as errors
from
    seconds left outer join errors on errors.second == seconds.second
    group by seconds.second

