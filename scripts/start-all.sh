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

# Kill any existing orchestrator processes
pkill -f "orchestrator.main" 2>/dev/null || true
sleep 1

# Start orchestrator in background with output logging
nohup python -m orchestrator.main > logs/orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > /tmp/strix-orchestrator.pid

# Wait for orchestrator to be ready
echo "Waiting for orchestrator to start..."
for i in {1..30}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "✓ Orchestrator is ready!"
        break
    fi
    sleep 1
    echo -n "."
done

# Check if orchestrator started successfully
if ! curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo ""
    echo "ERROR: Orchestrator failed to start!"
    echo "Check logs: tail -f logs/orchestrator.log"
    echo "Trying to start anyway..."
fi

# Start web manager
echo ""
echo "Starting web manager..."
nohup python web-manager/app.py > logs/web-manager.log 2>&1 &
WEB_PID=$!
echo $WEB_PID > /tmp/strix-web.pid

# Wait for web manager
sleep 2

echo ""
echo "========================================"
echo "Services started!"
echo "========================================"
echo ""
echo "Orchestrator: http://localhost:8080"
echo "Web Manager:  http://localhost:80"
echo ""
echo "Check status:"
echo "  curl http://localhost:8080/health"
echo ""
echo "View logs:"
echo "  tail -f logs/orchestrator.log"
echo "  tail -f logs/web-manager.log"
echo ""
echo "To stop: ./scripts/stop-all.sh"
