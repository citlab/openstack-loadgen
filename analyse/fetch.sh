#!/bin/bash
set -e
home=`dirname $(readlink -e $0)`
test $# -ge 2 || { echo "Parameters: <tablename> <hosts>*"; exit 1; }

tablename="$1"
shift 1
hosts="$@"

function fetch_host() {
    local host="$1"
    local path='openstack-loadgen/testing2'
    file=`ssh $host "ls -t -1 '$path' | head -1"`
    scp "$host:$path/$file" "$host.db"
}

for host in $hosts; do
    fetch_host $host
    $home/analyse.sh $tablename "$host.db"
done

$home/combine.sh $tablename $hosts
$home/analyse.sh $tablename combined.db

