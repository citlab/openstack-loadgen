#!/bin/bash
home=`dirname $(readlink -e $0)`

# If no file is given, use the newest *.db file in current directory.
file="$1"
if [ ! -f "$file" ]; then
    file="`ls -t -1 tests.sqlite.*.db | head -1`"
    test -f "$file" || { echo No *.db file found in current directory, please provide as parameter; exit 1; }
fi
echo Using database file $file

echo Executing analyse.sql
sqlite3 -bail "$file" < "$home/analyse.sql"

python ../analyse.py "$file"
