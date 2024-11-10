#!/bin/bash

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <packetloss>"
    exit 1
fi

sudo ip netns exec ns1 tc qdisc del dev veth1 root &> /dev/null
sudo ip netns exec ns2 tc qdisc del dev veth2 root &> /dev/null
sudo ip netns exec ns3 tc qdisc del dev veth3 root &> /dev/null
sudo ip netns exec ns4 tc qdisc del dev veth4 root &> /dev/null

sudo ip netns exec ns1 tc qdisc add dev veth1 root netem loss $1
sudo ip netns exec ns2 tc qdisc add dev veth2 root netem loss $1
sudo ip netns exec ns3 tc qdisc add dev veth3 root netem loss $1
sudo ip netns exec ns4 tc qdisc add dev veth4 root netem loss $1

sudo ip netns exec ns1 tc qdisc show dev veth1
sudo ip netns exec ns2 tc qdisc show dev veth2
sudo ip netns exec ns3 tc qdisc show dev veth3
sudo ip netns exec ns4 tc qdisc show dev veth4
