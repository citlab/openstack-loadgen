
update minsecond set offset = second-(select min(second) from minsecond);

update keystone2 set
    second = second+(select min(offset) from minsecond B where B.system = keystone2.system),
    start = start+(select min(offset) from minsecond B where B.system = keystone2.system),
    end = end+(select min(offset) from minsecond B where B.system = keystone2.system);
update active_requests set
    second = second+(select min(offset) from minsecond B where B.system = active_requests.system),
    start = start+(select min(offset) from minsecond B where B.system = active_requests.system),
    end = end+(select min(offset) from minsecond B where B.system = active_requests.system);

-- This should be fine as long as all test-systems are started within a minute.
--update active_requests_minutes set
--    minute = minute+(select min(offset) from minsecond B where B.system = active_requests_minutes.system),
--    start = start+(select min(offset) from minsecond B where B.system = active_requests_minutes.system),
--    end = end+(select min(offset) from minsecond B where B.system = active_requests_minutes.system);

