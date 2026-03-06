#!/bin/bash
# Start all Strix Consensus Server services

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting Strix Consensus Server..."
echo ""

# Start nginx (requires sudo)
echo "Starting nginx (port 80)..."
if command -v systemctl &> /dev/null && pidof systemd > /dev/null 2>&1; then
    sudo systemctl start nginx
elif command -v service &> /dev/null; then
    sudo service nginx start
elif command -v nginx &> /dev/null; then
    sudo nginx
else
    echo "WARNING: Could not start nginx automatically. Please start it manually."
fi

# Start orchestrator
echo "Starting orchestrator..."
cd "$PROJECT_DIR"
source venv/bin/activate

# Start orchestrator in background
python -m orchestrator.main &
ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > /tmp/strix-orchestrator.pid

# Wait for orchestrator to be ready
echo "Waiting for orchestrator to start..."
sleep 5

# Start web manager
echo "Starting web manager..."
python web-manager/app.py &
WEB_PID=$!
echo $WEB_PID > /tmp/strix-web.pid

echo ""
echo "Services started!"
echo ""
echo "Orchestrator: http://localhost:8080"
echo "Web Manager: http://localhost:80"
echo ""
echo "To stop services: ./scripts/stop-all.sh"
