sudo podman run --rm -d \
  --name "von-node1" \
  -v "/home/ant0n/von-network/node1-data:/home/indy/ledger" \
  -p "0.0.0.0:9701:9701/tcp" \
  -p "0.0.0.0:9702:9702/tcp" \
  -e "IP=" \
  -e "IPS=" \
  -e "DOCKERHOST=host.docker.internal" \
  -e "LOG_LEVEL=info" \
  -e "RUST_LOG=warning" \
  "localhost/von-network-base" \
  "./scripts/start_node.sh" "1"
sudo podman run --rm -d \
  --name "von-node2" \
  -v "/home/ant0n/von-network/node2-data:/home/indy/ledger" \
  -p "0.0.0.0:9703:9703/tcp" \
  -p "0.0.0.0:9704:9704/tcp" \
  -e "IP=" \
  -e "IPS=" \
  -e "DOCKERHOST=host.docker.internal" \
  -e "LOG_LEVEL=info" \
  -e "RUST_LOG=warning" \
  "localhost/von-network-base" \
  "./scripts/start_node.sh" "2"
sudo podman run --rm -d \
  --name "von-node3" \
  -v "/home/ant0n/von-network/node3-data:/home/indy/ledger" \
  -p "0.0.0.0:9705:9705/tcp" \
  -p "0.0.0.0:9706:9706/tcp" \
  -e "IP=" \
  -e "IPS=" \
  -e "DOCKERHOST=host.docker.internal" \
  -e "LOG_LEVEL=info" \
  -e "RUST_LOG=warning" \
  "localhost/von-network-base" \
  "./scripts/start_node.sh" "3"
sudo podman run --rm -d \
  --name "von-node4" \
  -v "/home/ant0n/von-network/node4-data:/home/indy/ledger" \
  -p "0.0.0.0:9707:9707/tcp" \
  -p "0.0.0.0:9708:9708/tcp" \
  -e "IP=" \
  -e "IPS=" \
  -e "DOCKERHOST=host.docker.internal" \
  -e "LOG_LEVEL=info" \
  -e "RUST_LOG=warning" \
  "localhost/von-network-base" \
  "./scripts/start_node.sh" "4"

sudo podman run --rm -d \
  --name "von-webserver" \
  -v "/home/ant0n/von-network/server:/home/indy/server:rw" \
  -v "/home/ant0n/von-network/config:/home/indy/config:rw" \
  -v "/home/ant0n/von-network/webserver-cli:/home/indy/.indy-cli" \
  -v "/home/ant0n/von-network/webserver-ledger:/home/indy/ledger" \
  -p "0.0.0.0:8000:8000/tcp" \
  -e "IP=" \
  -e "IPS=" \
  -e "DOCKERHOST=host.docker.internal" \
  -e "LOG_LEVEL=info" \
  -e "GENESIS_URL=" \
  -e "LEDGER_SEED=000000000000000000000000Trustee1" \
  -e "LEDGER_CACHE_PATH=" \
  -e "MAX_FETCH=50000" \
  -e "RESYNC_TIME=120" \
  -e "POOL_CONNECTION_ATTEMPTS=5" \
  -e "POOL_CONNECTION_DELAY=10" \
  -e "REGISTER_NEW_DIDS=True" \
  -e "LEDGER_INSTANCE_NAME=localhost" \
  -e "WEB_ANALYTICS_SCRIPT=" \
  "localhost/von-network-base" \
  "bash" "-c" "sleep 10 && ./scripts/start_webserver.sh"
