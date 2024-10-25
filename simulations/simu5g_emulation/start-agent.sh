#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <number>"
    exit 1
fi
netns=$(( $1 + 1 ))
sudo podman run --rm -it --network "ns:/run/netns/ns$netns" ghcr.io/antoncuranz/didcomm-on-quic/agents agents.car.main "car$1s" --ip "192.168.$netns.2" --ledger http://192.168.1.2:8000
