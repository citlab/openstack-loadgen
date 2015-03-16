
create table errors (start integer, time integer, error text);
insert into errors (start, time, error) select start, request_time, error from keystone where error is not null;

CREATE TABLE keystone2 (start integer, time integer);
insert into keystone2 (start, time) select start, request_time from keystone where error is null;



