didcomm-on-quic
===

This repository contains the implementation part of the Master's thesis **Trusted communication using QUIC and DIDComm in constrained environments** by Leon Anton Curanz.

The implementation consists of three parts:
- An ACA-Py HTTP/3 transport utilizing the QUIC protocol
- Three ACA-Py controller applications (car, discovery, issuer)
- DIDComm protocols implementing exemplary Vehicular Communication services

## 📂 Repository structure

```sh
📁
├─📁 acapy-plugins    # Implemented ACA-Py plugins (HTTP/3 transport, videostreaming and filesharing DIDComm protocols)
├─📁 agents           # Controller applications interacting with ACA-Py (car, discovery, issuer)
├─📁 stream           # First minute of "Big Buck Bunny" (test video for videostreaming use case)
├─📁 certs            # Self-signed certificates used for TLS connections
├─📁 simulations      # Simulated OMNeT++ networks used for the evaluation
└─📁 wallets          # ACA-Py wallets persisting connections and credentials
```

## Building and Running

### Building container images

I recommend packaging the different components as a container image and running it using Docker or Podman.
My GitHub repository is configured to automatically build container images on every commit.
But this can also be done locally using the following command:

```sh
docker build . -t didcomm-on-quic/agents:latest
```

### Running the Agents

The built image can then be used to start the Agents in containers.
Shell commands and available arguments are listed below.

```sh
# USAGE: podman run -it ghcr.io/antoncuranz/didcomm-on-quic/agents \
#   agents.{car|discovery|issuer}.main <agent_identifier> [args...]

# Car Agent
podman run -it ghcr.io/antoncuranz/didcomm-on-quic/agents \
    agents.car.main car1 --ip 127.0.0.1 -p 8030 --receive-invitations --quic
    
# Discovery Service
podman run -it ghcr.io/antoncuranz/didcomm-on-quic/agents \
    agents.discovery.main discovery1 --ip 127.0.0.1 -p 8040 --broadcast-invitations --quic
    
# Issuer Agent
podman run -it ghcr.io/antoncuranz/didcomm-on-quic/agents \
    agents.issuer.main issuer1 --ip 127.0.0.1 -p 8050 --quic
```

| Argument                | Description                                                                          |
|-------------------------|--------------------------------------------------------------------------------------|
| --ip IP                 | IP address to bind to (required argument)                                            |
| --port PORT             | Port to bind to (required argument)                                                  |
| --ledger URL            | Indy Ledger URL to connect to (Default value: http://test.bcovrin.vonx.io)           |
| --quic                  | Enable HTTP/3 transport                                                              |
| --broadcast-invitations | Regularly broadcast DIDComm invitations (only available for discovery agent)         |
| --receive-invitations   | Listen for and accept broadcasted DIDComm invitations (only available for car agent) |
| --keepalive TIMEOUT     | Timeout in seconds after which HTTP connections are closed (Default value: 15)       |
| --force-close           | Close HTTP connections directly after every request                                  |

## Test Setup

The folder `simulations/scripts` contains several scripts for setting up a Linux system for the network simulation tests.

### Preparation

The script `setup-veth.sh` creates four linux network namespaces `ns{1-4}` and virtual ethernet links `veth{1-4}`.
This script needs to be run before starting OMNeT++ network simulations.

The script `start-von.sh` starts four Indy nodes using the VON network in the `ns1` network namespace using Podman.
The image names and volume mounts probably need to be adjusted.

The script `setup-packetloss.sh` can be used to configure a specified amount of packetloss at virtual ethernet link interfaces.

#### Simulated Networks

The simulated networks used in this thesis are located in the `simulations` folder and can simply be copied to a OMNeT++ project.
The tests were performed with OMNeT++ 6.0.3 and INET framework 4.5.4.
Note that the `Network emulation support` Project Feature needs to be enabled in INET framework.

### Starting the Simulation

A simulated network can be started by right-clicking the respective `omnetpp.ini` file and clicking `Run As > OMNeT++ Simulation`. Then, click the three green arrows (Express Run) in the GUI.

The scripts `start-agent.sh` and `start-issuer.sh` can be used to start the respective agents in a specified network namespace.
