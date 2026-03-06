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

# Stop nginx
sudo systemctl stop nginx

echo ""
echo "All services stopped."
