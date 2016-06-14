#!/usr/bin/env bash
# This script needs to run in the container

addtime() {
    while IFS= read -r line; do
        echo "$(date +%s%N | cut -b1-13) $line"
    done
}

cd /code/scripts

MY_IP_ADDR=$(ifconfig eth0 | grep "inet addr" | cut -d ':' -f 2 | cut -d ' ' -f 1)
TMP=$(dig -x $MY_IP_ADDR +short)
MY_NAME=(${TMP//./ })

# wait for all peers
sleep 4m

echo 'Starting epto peer'
exec java -Xms50m -Xmx100m -cp ../build/libs/epto-1.0-SNAPSHOT-all.jar epto.utilities.App $MY_NAME | addtime > localhost.txt 2>&1
