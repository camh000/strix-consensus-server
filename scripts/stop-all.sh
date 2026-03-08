#!/bin/bash
# Stop all Strix Consensus Server services

set -e

echo "Stopping Strix Consensus Server..."

# Stop web manager
if [ -f /tmp/strix-web.pid ]; then
    echo "Stopping web manager..."
    kill $(cat /tmp/strix-web.pid) 2>/dev/null || true
    rm /tmp/strix-web.pid
fi

# Stop orchestrator
if [ -f /tmp/strix-orchestrator.pid ]; then
    echo "Stopping orchestrator..."
    kill $(cat /tmp/strix-orchestrator.pid) 2>/dev/null || true
    rm /tmp/strix-orchestrator.pid
fi

# Kill any orphaned llama-server worker processes
echo "Stopping llama-server workers..."
pkill -f llama-server 2>/dev/null || true

# Give processes a moment to exit, then force-kill any survivors
sleep 2
pkill -9 -f llama-server 2>/dev/null || true

# Stop nginx
echo "Stopping nginx..."
if command -v systemctl &> /dev/null && pidof systemd > /dev/null 2>&1; then
    sudo systemctl stop nginx 2>/dev/null || true
elif command -v service &> /dev/null; then
    sudo service nginx stop 2>/dev/null || true
elif [ -f /var/run/nginx.pid ]; then
    sudo kill $(cat /var/run/nginx.pid) 2>/dev/null || true
else
    sudo pkill nginx 2>/dev/null || true
fi

echo ""
echo "All services stopped."
