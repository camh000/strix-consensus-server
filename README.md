# Strix Consensus Server

A local AI model server with multi-model consensus support, tool execution, and web-based management for your AMD Strix Halo mini PC.

## Features

- **Multi-Model Consensus**: Run multiple LLMs simultaneously and use a judge model to select the best response
- **Mode Toggle**: Switch between single model (fast) and consensus mode (quality) via web interface
- **Full Tool Support**: Execute all OpenCode tools locally (file operations, commands, web search, etc.)
- **Web Management**: Port 80 interface for model management, logs, and mode control
- **AMD GPU Optimized**: Pre-configured for Strix Halo's Radeon graphics with ROCm/HIP support
- **Auto-Start Services**: Systemd services for automatic startup on boot

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCode (Your PC)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Consensus Orchestrator (:8080)                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Mode: Single / Consensus (N workers + Judge)      │   │
│  │  Tool Executor: All OpenCode tools available       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Worker 1    │  │  Worker 2    │  │  Judge       │
│  :8101       │  │  :8102       │  │  :8200       │
└──────────────┘  └──────────────┘  └──────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           Web Manager (:80) - Model & Mode Control          │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Windows 11 with WSL2 enabled
- AMD Strix Halo mini PC (or any AMD GPU system)
- At least 16GB RAM (32GB+ recommended)
- 50GB+ free disk space for models

### Installation

1. **Clone this repository on your Strix Halo:**
   ```bash
   git clone https://github.com/yourusername/strix-consensus-server.git
   cd strix-consensus-server
   ```

2. **Run the installation script:**
   ```bash
   ./scripts/install.sh
   ```
   This will:
   - Update WSL2 and install Ubuntu 22.04
   - Install ROCm/HIP for AMD GPU support
   - Build llama.cpp with GPU acceleration
   - Install Python dependencies
   - Configure systemd services

3. **Start the services:**
   ```bash
   ./scripts/start-all.sh
   ```

4. **Access the web interface:**
   Open `http://your-strix-ip` in your browser

### Configuration

Edit `.env` file to customize:

```env
# Number of worker models (1-5)
WORKER_COUNT=3

# Models to use (from HuggingFace)
WORKER_1_MODEL=unsloth/Llama-3.1-8B-Instruct-GGUF
WORKER_2_MODEL=Qwen/Qwen2.5-7B-Instruct-GGUF
WORKER_3_MODEL=deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct-GGUF
JUDGE_MODEL=unsloth/Llama-3.1-8B-Instruct-GGUF

# Quantization level (Q4_K_M recommended for balance)
QUANTIZATION=Q4_K_M

# Ports
ORCHESTRATOR_PORT=8080
WEB_MANAGER_PORT=5000
```

## Using with OpenCode

1. **Copy the configuration file** to your OpenCode config directory:
   ```bash
   # On your local machine (not the Strix Halo)
   cp config/opencode.json ~/.config/opencode/opencode.json
   ```

2. **Update the IP address** in `opencode.json`:
   ```json
   "baseURL": "http://YOUR_STRIX_IP:8080/v1"
   ```

3. **Restart OpenCode** - your local models will appear in `/models`

## Web Interface Features

### Dashboard (`http://your-strix-ip`)

- **Mode Toggle**: Switch between Single and Consensus mode
- **Model Management**: View status of all workers and judge
- **Performance Metrics**: Latency, throughput, consensus quality
- **Download Models**: HuggingFace integration for easy model downloads

### Operating Modes

**Single Model Mode:**
- Select one active model from dropdown
- Fastest response time
- No consensus overhead
- Good for: Quick iterations, testing, when speed matters

**Consensus Mode:**
- Configure 1-5 worker models
- Judge evaluates all responses
- Returns best answer with reasoning
- Good for: Critical tasks, code reviews, complex problems

## Tool Support

The orchestrator supports all OpenCode tools:

| Tool | Description | Example |
|------|-------------|---------|
| `file_read` | Read file contents | Read source code |
| `file_write` | Write/modify files | Save generated code |
| `file_search` | Search files by pattern | Find all .py files |
| `bash` | Execute shell commands | Run git status |
| `web_search` | Web search | Find documentation |
| `web_fetch` | Fetch web content | Read API docs |
| `code_execute` | Run code in sandbox | Test Python snippets |

## Model Recommendations

For Strix Halo (16-32GB shared memory):

### Small Models (Fast, 2-3 concurrent)
- **Llama 3.2 3B** - General purpose
- **Qwen 2.5 3B** - Coding tasks
- **Gemma 2 2B** - Efficient

### Medium Models (Balanced, 1-2 concurrent)
- **Llama 3.1 8B** - Best overall
- **Qwen 2.5 7B** - Excellent coding
- **DeepSeek Coder 6.7B** - Specialized coding

### Quantization Guide

| Quant | Size | Quality | Speed | Recommendation |
|-------|------|---------|-------|----------------|
| Q8_0 | ~8GB | Best | Slower | Judge model |
| Q6_K | ~6GB | Great | Good | Workers |
| Q4_K_M | ~5GB | Good | Fast | Workers (recommended) |
| Q3_K_M | ~4GB | Okay | Fastest | Testing only |

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `install.sh` | Initial setup - run once |
| `start-all.sh` | Start all services |
| `stop-all.sh` | Stop all services |
| `add-model.sh <name> <hf-repo>` | Add new model worker |
| `restart-orchestrator.sh` | Reload config without restart |

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues.

## Architecture Details

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design documentation.

## License

MIT License - See LICENSE file

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing style
- Add tests for new features
- Update documentation

## Support

- GitHub Issues: Bug reports and feature requests
- Discussions: General questions and help
