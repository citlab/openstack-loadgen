#!/bin/bash
home=`dirname $(readlink -e $0)`
test $# = 1 -o $# = 2 || { echo 'Parameters: <table name to analyse> [.db file]'; exit 1; }
tablename="$1"
echo "Working on tablename $tablename"

analyses="basic agg_durations agg_errors error_rate agg_requests agg_all_requests requests_smoothed_2sec"
# analyses="$analyses active-requests/basic active-requests/..."

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

for a in $analyses; do
    sqlfile="$home/analyses/$a.sql"
    if [ -f "$sqlfile" ]; then
        echo "Running $a"
        analyse_tablename="analyse_`basename $a`"
        create_query=`cat "$sqlfile"`
        if [ "$analyse_tablename" == 'analyse_basic' ]; then
            query="$create_query;"
        else
            query="drop table if exists $analyse_tablename; create table $analyse_tablename as $create_query;"
        fi
        run_sql "$file" <<< "$query"
    else
        echo "Analysis script not found: $sqlfile"
    fi
done

