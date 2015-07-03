
select requests.second, cast(e as float)/(cast(e as float)+cast(r as float)) as error_rate
    from (
        (select seconds.second, count(*) as r from 
            seconds left outer join requests on seconds.second == requests.second
            group by seconds.second) as requests 
        join 
        (select seconds.second, count(*) as e from 
            seconds left outer join errors on seconds.second == errors.second
            group by seconds.second) as errors 
        on requests.second == errors.second
    )

