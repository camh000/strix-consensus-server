#!/bin/bash
# Add a new model worker

if [ $# -lt 2 ]; then
    echo "Usage: $0 <worker_name> <huggingface_repo> [port]"
    echo "Example: $0 worker-4 microsoft/Phi-3-mini-4k-instruct-GGUF"
    exit 1
fi

WORKER_NAME=$1
MODEL_REPO=$2
PORT=${3:-0}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Adding worker: $WORKER_NAME"
echo "Model: $MODEL_REPO"
echo "Port: $PORT (0 = auto-assign)"

# Source environment
source "$PROJECT_DIR/.env" 2>/dev/null || true

# Add to configuration
cd "$PROJECT_DIR"
source venv/bin/activate

python3 << EOF
import json
import sys

config_file = 'config/runtime_config.json'

with open(config_file, 'r') as f:
    config = json.load(f)

# Find next available port
if $PORT == 0:
    used_ports = [w['port'] for w in config['workers']]
    port = max(used_ports, default=8100) + 1
else:
    port = $PORT

# Add new worker
config['workers'].append({
    'id': '$WORKER_NAME',
    'model': '$MODEL_REPO',
    'port': port,
    'enabled': True
})

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print(f"Added worker $WORKER_NAME on port {port}")
EOF

echo ""
echo "Worker added! Restart services to apply changes:"
echo "  ./scripts/stop-all.sh && ./scripts/start-all.sh"
