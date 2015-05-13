
home=`readlink -e $(dirname $0)`
test $# -ge 1 || { echo "Parameters: <host>*. Need <host>.db files in current directory."; exit 1; }
hosts="$@"
combined=combined.db

# Create sql script to combine all sub-results into one database
scriptpart=`cat $home/combine.sql`
script=
for h in $hosts; do
    test -f "$h".db || { echo File "$h".db not found; exit 1; }
    subscript=${scriptpart//HOST/$h}
    script="$script

$subscript"
done

echo Executing generated combine sql-script...
echo "$script" | sqlite3 -bail "$combined"
echo Executing combine2.sql
sqlite3 -bail "$combined" < "$home"/combine2.sql
echo Executing analyse.sql...
sqlite3 -bail "$combined" < "$home"/analyse.sql

