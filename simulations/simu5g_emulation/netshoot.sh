#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <netns>"
    exit 1
fi
sudo podman run --rm -it --network "ns:/run/netns/$1" ghcr.io/nicolaka/netshoot:v0.13
