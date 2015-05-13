
attach "HOST.db" as HOST;

create table if not exists errors (start integer, request_time integer, error text, system text);
insert into errors select *, "HOST" as system from HOST.errors;

create table if not exists seconds (second integer, system text);
insert into seconds select *, "HOST" as system from HOST.seconds A where not exists (select 1 from seconds B where A.second == B.second);

create table if not exists minsecond (second integer, system text, offset integer);
insert into minsecond select second, "HOST" as system, 0 as offset from HOST.minsecond;

create table if not exists keystone (start integer, request_time integer, error text, system text);
insert into keystone select *, "HOST" as system from HOST.keystone;

create table if not exists keystone2 (second integer, start integer, end integer, time integer, system text);
insert into keystone2 select *, "HOST" as system from HOST.keystone2;

create table if not exists active_requests (second integer, start integer, end integer, time integer, system text);
insert into active_requests select *, "HOST" as system from HOST.active_requests;

create table if not exists active_requests_minutes (minute integer, start integer, end niteger, time integer, system text);
insert into active_requests_minutes select *, "HOST" as system from HOST.active_requests_minutes;

