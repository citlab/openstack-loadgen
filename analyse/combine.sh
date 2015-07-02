#!/bin/bash
set -e
home=`readlink -e $(dirname $0)`
test $# -ge 2 || { echo "Parameters: <tablename> <hosts to combine>*."; exit 1; }
tablename="$1"
shift 1
hosts="$@"
combined=combined.db
echo "Using tablename $tablename"

function run_sql() {
    test -z "$tablename" && tablename="SOURCETABLE"
    dbfile="$1"
    sed -s "s/SOURCETABLE/$tablename/g" | sqlite3 -bail "$dbfile"
}

# Create sql script to combine all sub-results into one database
scriptpart=`cat $home/combine-part1.sql`
script=
for h in $hosts; do
    test -f "$h".db || { echo File "$h".db not found; exit 1; }
    subscript=${scriptpart//HOST/$h}
    script="$script

$subscript"
done

echo "Executing generated combine sql-script..."
echo "$script" | run_sql "$combined"
echo "Executing combine-part2.sql"
run_sql "$combined" < "$home/combine-part2.sql"

