#!/bin/bash
sqlite3 `ls -t -1 tests.sqlite.*.db | head -1` 'select * from keystone order by start;'
