#!/bin/bash
home=`dirname $(readlink -e $0)`
test $# = 1 -o $# = 2 || { echo 'Parameters: <table name to analyse> [.db file]'; exit 1; }
tablename="$1"

function run_sql() {
    test -z "$tablename" && tablename="SOURCETABLE"
    dbfile="$1"
    sed -s "s/SOURCETABLE/$tablename/g" | sqlite3 -bail "$dbfile"
}

# If no file is given, use the newest *.db file in current directory.
file="$2"
if [ ! -f "$file" ]; then
    file=`ls -t -1 tests.sqlite.*.db 2> /dev/null | head -1`
    test -f "$file" || { echo "No *.db file found in current directory, please provide as parameter"; exit 1; }
fi
echo "Using database file $file"

echo "Executing analyse.sql (using table $tablename)"
cat "$home/analyse.sql" | run_sql "$file"

python "$home/analyse.py" "$file"
