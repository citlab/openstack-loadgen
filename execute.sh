
test $# -gt 1 || { echo Need 1 parameter: target host; exit 1; }
target="$1"
host=`hostname`

exec &> "$host".out

python ../keystone.py "$target"
mv tests.sqlite.*.db "$host".db
../analyse.sh "$host".db

