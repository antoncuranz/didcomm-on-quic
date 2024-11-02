#!/bin/bash

# Define your commands here
COMMAND1="./start-agent.sh 1 ${@}"
COMMAND2="./start-agent.sh 2 ${@}"

# Create a new tmux session
tmux new-session -d -s agents

# Split the window horizontally
tmux split-window -h

# Send the first command to the left pane
tmux send-keys -t agents:0.0 "$COMMAND1; tmux wait -S done" C-m

# Send the second command to the right pane
tmux send-keys -t agents:0.1 "$COMMAND2; tmux wait -S done" C-m

cleanup() {
    sudo podman rm -f -t 0 car1s
    sudo podman rm -f -t 0 car2s
    tmux kill-session -t agents
}

# Monitor the commands and trigger cleanup on exit
(tmux wait done && cleanup) &

# Attach to the session
tmux attach-session -t agents

