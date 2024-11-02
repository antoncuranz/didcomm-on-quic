#!/bin/bash

sudo podman run --rm -it --name "issuer1" --network "ns:/run/netns/ns1" ghcr.io/antoncuranz/didcomm-on-quic/agents agents.issuer.main "issuer1" --ip "192.168.1.2" --ledger http://192.168.1.2:8000
