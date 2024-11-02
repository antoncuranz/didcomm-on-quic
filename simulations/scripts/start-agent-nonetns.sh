#!/bin/bash

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <number> [OPTS]"
    exit 1
fi

p=$(( $1 + 1 ))

sudo podman run --rm -it \
    --name "car$1" \
    -p "80${p}0:80${p}0" \
    -p "80${p}0:80${p}0/udp" \
    -v "/home/ant0n/dash/pluge_490K:/usr/src/app/stream" \
    ghcr.io/antoncuranz/didcomm-on-quic/agents agents.car.main "car$1" --ip "192.168.108.4" --port "80${p}0" ${@:2}
