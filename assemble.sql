
attach "HOST.db" as HOST;

create table if not exists errors (start integer, request_time integer, error text);
insert into errors select * from HOST.errors;

create table if not exists seconds (second integer);
insert into seconds select * from HOST.seconds A where not exists (select 1 from seconds B where A.second == B.second);

create table if not exists minsecond (second integer, system text);
insert into minsecond select second, "HOST" as system from HOST.minsecond;

create table if not exists keystone (start integer, request_time integer, error text);
insert into keystone select * from HOST.keystone;

create table if not exists keystone2 (second integer, start integer, end integer, time integer);
insert into keystone2 select * from HOST.keystone2;

create table if not exists active_requests (second integer, start integer, end integer, time integer);
insert into active_requests select * from HOST.active_requests;

create table if not exists active_requests_minutes (minute integer, start integer, end niteger, time integer);
insert into active_requests_minutes select * from HOST.active_requests_minutes;

