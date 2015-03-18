
target="$1"
host=`hostname`

exec &> "$host".out

python ../keystone.py "$target"
mv tests.sqlite.*.db "$host".db
../analyse.sh "$host".db

