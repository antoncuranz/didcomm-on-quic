#!/bin/bash
#   
#   
#   +++++++++++++++++++++++++     +++++++++++++++++++++++++     +++++++++++++++++++++++++
#   +     Namespace ns1     +     +         Simu5G        +     +     Namespace ns2     +
#   +                       +     +                       +     +                       +
#   +  Client App     [veth1]<--->[sim-veth1]   [sim-veth2]<--->[veth2]     Server App  +
#   +            192.168.2.2+     +                       +     +192.168.3.2            +
#   +                       +     +                       +     +                       +
#   +++++++++++++++++++++++++     +++++++++++++++++++++++++     +++++++++++++++++++++++++
#   

# create two namespaces
sudo ip netns add ns1
sudo ip netns add ns2
sudo ip netns add ns3
sudo ip netns add ns4

# create virtual ethernet link: ns1.veth1 <--> sim-veth1 , sim-veth2 <--> ns2.veth2 
sudo ip link add veth1 netns ns1 type veth peer name sim-veth1
sudo ip link add veth2 netns ns2 type veth peer name sim-veth2
sudo ip link add veth3 netns ns3 type veth peer name sim-veth3
sudo ip link add veth4 netns ns4 type veth peer name sim-veth4

# Assign the address 192.168.1.2 with netmask 255.255.255.0 to `veth1`
sudo ip netns exec ns1 ip addr add 192.168.1.2/24 dev veth1
sudo ip netns exec ns2 ip addr add 192.168.2.2/24 dev veth2
sudo ip netns exec ns3 ip addr add 192.168.3.2/24 dev veth3
sudo ip netns exec ns4 ip addr add 192.168.4.2/24 dev veth4

# bring up all interfaces
sudo ip netns exec ns1 ip link set veth1 up
sudo ip netns exec ns1 ip link set dev lo up
sudo ip netns exec ns2 ip link set veth2 up
sudo ip netns exec ns2 ip link set dev lo up
sudo ip netns exec ns3 ip link set veth3 up
sudo ip netns exec ns3 ip link set dev lo up
sudo ip netns exec ns4 ip link set veth4 up
sudo ip netns exec ns4 ip link set dev lo up
sudo ip link set sim-veth1 up
sudo ip link set sim-veth2 up
sudo ip link set sim-veth3 up
sudo ip link set sim-veth4 up

# add default IP route within new namespaces 
sudo ip netns exec ns1 route add default dev veth1
sudo ip netns exec ns2 route add default dev veth2
sudo ip netns exec ns3 route add default dev veth3
sudo ip netns exec ns4 route add default dev veth4

# disable TCP checksum offloading to make sure that TCP checksum is actually calculated
sudo ip netns exec ns1 ethtool --offload veth1 rx off tx off 
sudo ip netns exec ns2 ethtool --offload veth2 rx off tx off 
sudo ip netns exec ns3 ethtool --offload veth3 rx off tx off 
sudo ip netns exec ns4 ethtool --offload veth4 rx off tx off 

# fix packet fragmentation problems
sudo ip netns exec ns1 ip link set dev veth1 mtu 1300
sudo ip netns exec ns2 ip link set dev veth2 mtu 1300
sudo ip netns exec ns3 ip link set dev veth3 mtu 1300
sudo ip netns exec ns4 ip link set dev veth4 mtu 1300
