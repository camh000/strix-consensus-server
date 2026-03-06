#!/bin/bash
# Restart orchestrator to apply config changes

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Restarting orchestrator to apply config changes..."

# Kill orchestrator
if [ -f /tmp/strix-orchestrator.pid ]; then
    kill $(cat /tmp/strix-orchestrator.pid) 2>/dev/null || true
    rm /tmp/strix-orchestrator.pid
fi

# Wait a moment
sleep 2

# Start again
cd "$PROJECT_DIR"
source venv/bin/activate

python -m orchestrator.main &
ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > /tmp/strix-orchestrator.pid

echo "Orchestrator restarted!"
