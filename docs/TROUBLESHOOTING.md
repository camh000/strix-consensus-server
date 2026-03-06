# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### ROCm Installation Fails

**Problem**: ROCm packages fail to install

**Solutions**:
1. Check WSL2 version: `wsl --version` (needs WSL2)
2. Update WSL: `wsl --update`
3. Check Ubuntu version: `lsb_release -a` (needs 22.04+)
4. Manual ROCm install:
   ```bash
   sudo apt update
   sudo apt install -y rocm-dev
   ```

#### llama.cpp Build Errors

**Problem**: CMake configuration fails

**Solutions**:
1. Check dependencies:
   ```bash
   sudo apt install -y build-essential cmake ninja-build
   ```
2. Check HIP installation:
   ```bash
   which hipcc
   hipcc --version
   ```
3. Clean and rebuild:
   ```bash
   cd ~/llama.cpp
   rm -rf build
   cmake -B build -DGGML_HIP=ON
   cmake --build build
   ```

### Runtime Issues

#### Models Won't Start

**Problem**: Workers show "stopped" or fail to start

**Check**:
```bash
# Check llama-server is in PATH
which llama-server

# Check GPU is detected
rocminfo | grep "Name:"

# Check available memory
free -h
```

**Solutions**:
1. Reduce GPU layers: Set `N_GPU_LAYERS=20` in .env
2. Reduce context size: Set `CONTEXT_SIZE=8192`
3. Use smaller models (3B instead of 7B)

#### Out of Memory Errors

**Problem**: GPU or system runs out of memory

**Solutions**:
1. Reduce worker count in .env: `WORKER_COUNT=2`
2. Use lower quantization: `QUANTIZATION=Q3_K_M`
3. Disable flash attention: Set `FLASH_ATTENTION=false`
4. Enable memory mapping: Set `MMAP=true`

#### High Latency

**Problem**: Responses take too long

**Solutions**:
1. Switch to Single Mode via web UI
2. Reduce worker count in consensus mode
3. Disable judge evaluation
4. Use smaller/faster models
5. Check GPU utilization: `rocm-smi`

### Connection Issues

#### OpenCode Can't Connect

**Problem**: OpenCode shows connection errors

**Check**:
1. Verify orchestrator is running:
   ```bash
   curl http://localhost:8080/health
   ```
2. Check firewall (Windows Defender):
   - Allow port 8080 through firewall
3. Verify IP address in opencode.json matches Strix Halo IP

**Solutions**:
```bash
# On Strix Halo (WSL2), get IP
hostname -I

# Update opencode.json on client machine
"baseURL": "http://STRIX_IP:8080/v1"
```

#### Web Interface Not Loading

**Problem**: Can't access http://strix-ip

**Check**:
```bash
# Check nginx is running
sudo systemctl status nginx

# Check web manager
ps aux | grep "web-manager"

# Check ports
sudo netstat -tlnp | grep -E ':(80|5000|8080)'
```

**Solutions**:
1. Start nginx: `sudo systemctl start nginx`
2. Check nginx config: `sudo nginx -t`
3. Restart services: `./scripts/restart-all.sh`

### Tool Execution Issues

#### Tools Not Working

**Problem**: File operations or commands fail

**Check**:
1. Verify tool calls in orchestrator logs
2. Check file permissions
3. Review tool output in response

**Solutions**:
1. Grant permissions:
   ```bash
   chmod -R 755 ~/strix-consensus-server
   ```
2. Check path exists:
   ```bash
   ls -la /mnt/c/path/to/project
   ```

#### Bash Commands Timeout

**Problem**: Long-running commands fail

**Solutions**:
1. Increase timeout in tool_executor.py:
   ```python
   timeout=60  # Increase from 30
   ```
2. Run commands in background
3. Use shorter commands

### Consensus Issues

#### Judge Always Picks Same Worker

**Problem**: Consensus seems biased

**Solutions**:
1. Check judge model quality (use same or better than workers)
2. Review consensus logs for reasoning
3. Adjust judge prompt in judge.py
4. Try different judge model

#### Workers Return Different Formats

**Problem**: Inconsistent responses break judge evaluation

**Solutions**:
1. Use same chat template for all workers
2. Standardize output format in prompt
3. Add format instructions to system prompt

### Model Download Issues

#### Downloads Fail or Timeout

**Problem**: Can't download models from HuggingFace

**Solutions**:
1. Check internet connection
2. Use mirror: Set `MODEL_ENDPOINT=https://www.modelscope.cn/`
3. Manual download:
   ```bash
   cd ~/strix-consensus-server/models
   wget https://huggingface.co/username/model/resolve/main/model-Q4_K_M.gguf
   ```
4. Upload via web UI instead

#### Wrong Quantization Downloaded

**Problem**: Script downloads Q5 when you wanted Q4

**Solutions**:
1. Edit download function in model_pool.py
2. Specify exact filename in config
3. Manually download correct version

### Performance Optimization

#### Slow Token Generation

**Problem**: Low tokens/second

**Optimization Steps**:
1. Enable GPU layers: `N_GPU_LAYERS=-1` (all layers)
2. Enable flash attention: `FLASH_ATTENTION=true`
3. Use optimized build:
   ```bash
   cmake -B build -DGGML_HIP=ON -DCMAKE_BUILD_TYPE=Release
   ```
4. Reduce context size if not needed
5. Use smaller batch size if memory allows

#### High CPU Usage

**Problem**: CPU at 100% during inference

**Solutions**:
1. Increase GPU layers offloading
2. Check if GPU is being used: `rocm-smi`
3. Enable GPU acceleration properly
4. Reduce number of parallel workers

### Web Interface Issues

#### Mode Toggle Not Working

**Problem**: Can't switch between Single/Consensus mode

**Check**:
```bash
# Check orchestrator is responding
curl http://localhost:8080/api/status

# Check config file
ls -la config/runtime_config.json
```

**Solutions**:
1. Restart orchestrator: `./scripts/restart-orchestrator.sh`
2. Check browser console for JavaScript errors
3. Clear browser cache

#### Uploads Fail

**Problem**: Can't upload GGUF files

**Solutions**:
1. Check file size (max limit in Flask)
2. Ensure .gguf extension
3. Check disk space: `df -h`
4. Check permissions on models directory

### Systemd Service Issues

#### Services Won't Start

**Problem**: systemctl start fails

**Check logs**:
```bash
# User services
systemctl --user status strix-orchestrator
journalctl --user -u strix-orchestrator

# Nginx
sudo systemctl status nginx
sudo journalctl -u nginx
```

**Solutions**:
1. Check paths in service files
2. Ensure virtual environment exists
3. Check environment variables
4. Run manually to see errors:
   ```bash
   cd ~/strix-consensus-server
   source venv/bin/activate
   python -m orchestrator.main
   ```

#### Services Don't Auto-Start

**Problem**: Services not starting on boot

**Solutions**:
```bash
# Enable linger for user services
loginctl enable-linger $USER

# Enable services
systemctl --user enable strix-orchestrator
systemctl --user enable strix-web-manager
sudo systemctl enable nginx
```

### Debugging

#### Enable Debug Logging

**Python**:
```python
# In main.py
logging.basicConfig(level=logging.DEBUG)
```

**Environment**:
```bash
# In .env
LOG_LEVEL=DEBUG
```

#### Check All Logs

```bash
# Application logs
tail -f logs/*.log

# Systemd logs
journalctl --user -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

#### Test Components Individually

**Test orchestrator**:
```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/models
```

**Test worker**:
```bash
curl http://localhost:8101/health
curl -X POST http://localhost:8101/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "test", "messages": [{"role": "user", "content": "hi"}]}'
```

**Test web manager**:
```bash
curl http://localhost:5000/api/status
```

### Getting Help

If issues persist:

1. **Check GitHub Issues**: Search for similar problems
2. **Gather information**:
   ```bash
   # System info
   uname -a
   lsb_release -a
   rocminfo | head -20
   
   # Service status
   systemctl --user status
   
   # Recent logs
   journalctl --user --since "1 hour ago"
   ```
3. **Create minimal reproduction**: 
   - Single worker mode
   - Simple prompt
   - No tools

## Known Limitations

1. **No Authentication**: Designed for trusted networks
2. **No HTTPS**: HTTP only (add reverse proxy for HTTPS)
3. **Single Machine**: Workers must run on same host
4. **No Persistence**: Logs not automatically rotated
5. **Memory Constraints**: Limited by Strix Halo RAM

## Tips for Strix Halo

1. **Memory**: With 16GB shared memory, max 2-3 7B models
2. **GPU**: Use ROCm backend, not CUDA
3. **Cooling**: Monitor temps during long inference
4. **Power**: Consider power settings for 24/7 operation
