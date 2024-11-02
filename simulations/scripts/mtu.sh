# fix packet fragmentation problems
sudo ip netns exec ns1 ip link set dev veth1 mtu $1
sudo ip netns exec ns2 ip link set dev veth2 mtu $1
sudo ip netns exec ns3 ip link set dev veth3 mtu $1
sudo ip netns exec ns4 ip link set dev veth4 mtu $1
