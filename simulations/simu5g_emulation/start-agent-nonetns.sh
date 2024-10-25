sudo podman run --rm -it -p 8020:8020 ghcr.io/antoncuranz/didcomm-on-quic/agents agents.car.main cara --ip 192.168.108.4 --ledger http://192.168.108.4:8000 --receive-invitations
#sudo podman run --rm -it -p 8030:8030 ghcr.io/antoncuranz/didcomm-on-quic/agents agents.discovery.main discoverya --port 8030 --ip 192.168.108.4 --ledger http://192.168.108.4:8000 --broadcast-invitations
