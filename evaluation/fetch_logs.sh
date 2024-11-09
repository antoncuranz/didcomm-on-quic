if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <name> <containers...>"
    exit 1
fi

mkdir -p $1

for container in "${@:2}"; do
    log_file=$(ssh ant0n@192.168.64.2 "sudo podman exec $container ls logs")
    ssh ant0n@192.168.64.2 "sudo podman exec $container cat logs/$log_file" > $1/$log_file
done