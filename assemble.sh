
home=`readlink -e $(dirname $0)`
test $# -ge 2 || { echo "Parameters: <source-directory> <host>*"; exit 1; }

folder="$1"
shift 1
hosts="$@"

# Copy all sub-results to current directory
#for h in $hosts; do
#    scp $h:"$folder" .
#done

# Create sql script to combine all sub-results into one database
scriptpart=`cat $home/assemble.sql`
script=
for h in $hosts; do
    subscript=${scriptpart//HOST/$h}
    script="$script

$subscript"
done
echo Executing combine sql-script...
echo "$script" | sqlite3 -bail combined.db
echo Now executing analyse.sql...
sqlite3 -bail combined.db < "$home"/analyse.sql

