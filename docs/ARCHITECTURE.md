# Strix Consensus Server Architecture

## Overview

Strix Consensus Server is a multi-model LLM serving system with consensus-based response selection, designed specifically for AMD Strix Halo mini PCs.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   OpenCode  │  │   Web UI    │  │    API Clients          │  │
│  │  (Terminal) │  │   (Browser) │  │    (Any HTTP client)    │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          │                │                     │
          └────────────────┴─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Load Balancer   │
                    │   (Nginx :80)     │
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   ORCHESTRATOR  │ │   WEB MANAGER   │ │     STATIC      │
│    (:8080)      │ │    (:5000)      │ │     FILES       │
│                 │ │                 │ │                 │
│ ┌─────────────┐ │ │ ┌─────────────┐ │ │                 │
│ │   FastAPI   │ │ │ │    Flask    │ │ │                 │
│ │   Server    │ │ │ │   Dashboard │ │ │                 │
│ └──────┬──────┘ │ │ └─────────────┘ │ │                 │
│        │        │ └─────────────────┘ │                 │
│ ┌──────▼──────┐ │                     │                 │
│ │  Consensus  │ │                     │                 │
│ │   Engine    │ │                     │                 │
│ └──────┬──────┘ │                     │                 │
│        │        │                     │                 │
│ ┌──────▼──────┐ │                     │                 │
│ │    Judge    │ │                     │                 │
│ └──────┬──────┘ │                     │                 │
│        │        │                     │                 │
│ ┌──────▼──────┐ │                     │                 │
│ │    Tool     │ │                     │                 │
│ │  Executor   │ │                     │                 │
│ └─────────────┘ │                     │                 │
└────────┬────────┘                     │                 │
         │                              │                 │
         │                              │                 │
         ▼                              │                 │
┌───────────────────────────────────────┘                 │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│  │ Worker 1 │  │ Worker 2 │  │ Worker N │  │  Judge  │  │
│  │  :8101  │  │  :8102  │  │  :810N  │  │  :8200  │  │
│  │ llama-  │  │ llama-  │  │ llama-  │  │ llama-  │  │
│  │ server  │  │ server  │  │ server  │  │ server  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │
│                                                         │
│                    MODEL POOL                           │
└─────────────────────────────────────────────────────────┘
```

## Components

### 1. Orchestrator (main.py)

**Purpose**: Central request handler and coordinator

**Responsibilities**:
- OpenAI-compatible API endpoint (/v1/chat/completions)
- Mode switching (Single ↔ Consensus)
- Request routing and load balancing
- Tool call interception and execution

**Key Classes**:
- `FastAPI app`: Main HTTP server
- `handle_single_mode()`: Routes to single worker
- `handle_consensus_mode()`: Parallel dispatch to multiple workers

### 2. Consensus Engine (consensus_engine.py)

**Purpose**: Manages multi-model parallel execution

**Responsibilities**:
- Query multiple workers in parallel
- Timeout management
- Response collection
- Performance tracking

**Algorithm**:
```python
async def query_all_workers(prompt, worker_count):
    # 1. Select available workers
    workers = get_available_workers()[:worker_count]
    
    # 2. Create parallel tasks
    tasks = [query_worker(w, prompt) for w in workers]
    
    # 3. Execute concurrently
    responses = await asyncio.gather(*tasks)
    
    # 4. Return all responses
    return {worker.id: response for worker, response in zip(workers, responses)}
```

### 3. Judge (judge.py)

**Purpose**: Evaluates and selects best response

**Responsibilities**:
- Compare multiple responses
- Score on accuracy, completeness, clarity
- Provide reasoning for selection

**Evaluation Prompt**:
```
You are an expert evaluator. Rate each response 1-10 on:
1. Accuracy and correctness
2. Completeness of the answer  
3. Clarity and reasoning quality

Select the BEST response and explain why.
```

### 4. Tool Executor (tool_executor.py)

**Purpose**: Local execution of OpenCode tools

**Supported Tools**:
- `file_read/write/search/list`: File operations
- `bash`: System commands
- `web_search/fetch`: Internet access
- `code_execute`: Python/Node.js sandbox
- `git_*`: Version control operations

**Security**:
- Path traversal prevention
- Timeout limits
- Output size limits
- No network access from code sandbox

### 5. Model Pool (model_pool.py)

**Purpose**: Manages llama-server instances

**Responsibilities**:
- Start/stop model servers
- Model download from HuggingFace
- Port allocation
- Health monitoring

**Architecture**:
```
ModelPool
├── workers[]: List[Worker]
│   ├── worker-1: Llama-3.1-8B @ :8101
│   ├── worker-2: Qwen-2.5-7B @ :8102
│   └── worker-N: ... @ :810N
└── judge: Llama-3.1-8B @ :8200
```

### 6. Web Manager (app.py)

**Purpose**: Management dashboard on port 80

**Features**:
- Mode toggle (Single ↔ Consensus)
- Worker management
- Model download/upload
- Consensus logs viewer
- Performance metrics

**Routes**:
- `/`: Dashboard
- `/api/status`: System status
- `/api/mode`: Change mode
- `/api/models`: Available models

## Data Flow

### Single Mode Request

```
1. Client sends request to /v1/chat/completions
2. Orchestrator checks mode (single)
3. Routes to active worker
4. Worker processes request
5. If tools called:
   a. Tool executor runs locally
   b. Re-query with results
6. Returns response to client
```

### Consensus Mode Request

```
1. Client sends request to /v1/chat/completions
2. Orchestrator checks mode (consensus)
3. Consensus Engine queries N workers in parallel
4. All workers respond
5. If any tools called:
   a. Execute tools
   b. Re-query all workers
6. Judge evaluates all responses
7. Best response selected with reasoning
8. Returns to client with consensus_info
```

## Configuration

### Runtime Config (runtime_config.json)

```json
{
  "mode": "consensus",
  "single_mode": {
    "active_worker": "worker-1"
  },
  "consensus_mode": {
    "worker_count": 3,
    "use_judge": true
  },
  "workers": [...],
  "judge": {...}
}
```

**Hot Reload**: Config changes without restart via file watcher

### Environment (.env)

```bash
MODE=consensus
WORKER_COUNT=3
WORKER_1_MODEL=unsloth/Llama-3.1-8B-Instruct-GGUF
GPU_BACKEND=hip
N_GPU_LAYERS=-1
```

## Performance Considerations

### GPU Memory

- Each model loads into GPU VRAM
- Strix Halo: Shared memory architecture
- Q4_K_M quantized models: ~5GB each
- Recommend: 3 workers max for 16GB, 5 for 32GB

### Latency

**Single Mode**: ~50-100ms (model dependent)
**Consensus Mode**: 
- Parallel queries: Max(worker latencies)
- Judge evaluation: +100-200ms
- Total: ~150-400ms

### Optimization Strategies

1. **GPU Layer Offloading**: Use `-ngl` to control VRAM usage
2. **Flash Attention**: Enable for 2x speedup
3. **Context Size**: Reduce if memory constrained
4. **Worker Selection**: Disable unused workers
5. **Caching**: Judge evaluations can be cached

## Security Model

### Network
- Orchestrator binds to 0.0.0.0 (accessible from LAN)
- No authentication (assumed trusted network)
- Optional: Add API key in nginx config

### Tool Execution
- File operations restricted to project directory
- Bash commands timeout after 30s
- No sudo privileges
- Path traversal blocked

### Model Downloads
- Only from HuggingFace (HTTPS)
- GGUF format (safe, no code execution)
- Verify checksums before loading

## Deployment Options

### Option 1: Systemd Services (Recommended)

```bash
# Auto-start on boot
systemctl --user enable strix-orchestrator
systemctl --user enable strix-web-manager
```

### Option 2: Docker Compose

```bash
docker-compose up -d
```

### Option 3: Manual Start

```bash
./scripts/start-all.sh
```

## Monitoring

### Metrics Collected

- Request count (total, per mode)
- Latency (avg, p95, p99)
- Worker utilization
- GPU memory usage
- Token throughput

### Logging

- `logs/consensus_YYYYMMDD.jsonl`: Consensus decisions
- `logs/orchestrator.log`: Application logs
- Systemd journal: Service status

### Health Checks

- `/health`: Returns 200 if all systems operational
- Worker status: Online/offline per worker
- Model loading: Success/failure tracking

## Future Enhancements

1. **Weighted Consensus**: Different weights per worker
2. **Streaming Support**: SSE for real-time responses
3. **Model Hot-Swap**: Change models without restart
4. **Distributed Workers**: Workers on multiple machines
5. **Custom Judges**: Pluggable evaluation strategies
6. **Prompt Caching**: Cache common prompts
7. **A/B Testing**: Compare model versions
