#!/bin/bash

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <number> [OPTS]"
    exit 1
fi

netns=$(( $1 + 1 ))

sudo podman run --rm -it \
    --name "car$1s" \
    --network "ns:/run/netns/ns$netns" \
    -v "/home/ant0n/dash/pluge_61K:/usr/src/app/stream" \
    ghcr.io/antoncuranz/didcomm-on-quic/agents agents.car.main "car$1s" --ip "192.168.$netns.2" --ledger http://192.168.1.2:8000 ${@:2}
