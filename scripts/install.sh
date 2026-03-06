#!/bin/bash
# Installation script for Strix Consensus Server
# Run this on your Strix Halo (WSL2 Ubuntu)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$HOME/strix-consensus-server"
PYTHON_VERSION="3.10"

# Helper functions
print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running in WSL2
check_wsl() {
    print_step "Checking WSL2 environment..."
    
    if ! grep -q "microsoft" /proc/version 2>/dev/null; then
        print_error "This script must be run in WSL2"
        exit 1
    fi
    
    echo "✓ WSL2 detected"
}

# Update system
update_system() {
    print_step "Updating system packages..."
    sudo apt update && sudo apt upgrade -y
    echo "✓ System updated"
}

# Install dependencies
install_deps() {
    print_step "Installing dependencies..."
    
    sudo apt install -y \
        build-essential \
        cmake \
        git \
        python3 \
        python3-pip \
        python3-venv \
        wget \
        curl \
        ninja-build \
        libclblast-dev \
        libopenblas-dev
    
    echo "✓ Dependencies installed"
}

# Install ROCm for AMD GPU
install_rocm() {
    print_step "Setting up ROCm for AMD GPU..."
    
    # Check if ROCm is already installed
    if command -v rocminfo &> /dev/null; then
        print_warning "ROCm already installed, skipping..."
        return
    fi
    
    # Check for conflicting packages
    if dpkg -l | grep -E "rocm|hip" | grep -q "^ii"; then
        print_warning "Found existing ROCm packages with different versions"
        print_step "Removing conflicting packages..."
        sudo apt remove -y rocm-* hip-* || true
        sudo apt autoremove -y
        sudo apt update
    fi
    
    # Try installing ROCm with aptitude for better dependency resolution
    print_step "Installing ROCm (this may take a while)..."
    
    # Install aptitude if not present
    sudo apt install -y aptitude
    
    # Try to install with aptitude which handles dependencies better
    sudo aptitude install -y rocm-dev hip-dev || {
        print_warning "ROCm installation with aptitude failed"
        print_step "Trying alternative: Installing ROCm components individually..."
        
        # Install components individually
        sudo apt install -y rocm-core rocm-language-runtime rocm-llvm || true
        sudo apt install -y hip-dev || true
    }
    
    # Add user to render and video groups
    sudo usermod -a -G render,video $USER 2>/dev/null || true
    
    echo "✓ ROCm installation attempted"
    print_warning "You may need to log out and back in for group changes to take effect"
}

# Build llama.cpp
build_llama_cpp() {
    print_step "Building llama.cpp with HIP support..."
    
    if [ -d "$HOME/llama.cpp" ]; then
        print_warning "llama.cpp already exists, updating..."
        cd "$HOME/llama.cpp"
        git pull
    else
        cd "$HOME"
        git clone https://github.com/ggml-org/llama.cpp.git
        cd llama.cpp
    fi
    
    # Check if HIP is available
    if command -v hipcc &> /dev/null; then
        print_step "Building llama.cpp with HIP/AMD GPU support..."
        cmake -B build \
            -DGGML_HIP=ON \
            -DGGML_HIPBLAS=ON \
            -DCMAKE_C_COMPILER=clang \
            -DCMAKE_CXX_COMPILER=clang++ \
            -DLLAMA_CUDA=ON 2>&1 || {
            print_warning "HIP build failed, falling back to CPU-only build..."
            rm -rf build
            cmake -B build -DCMAKE_BUILD_TYPE=Release
        }
    else
        print_step "HIP not found, building llama.cpp with CPU support only..."
        cmake -B build -DCMAKE_BUILD_TYPE=Release
    fi
    
    cmake --build build --config Release -j$(nproc) || {
        print_error "Build failed. Trying with single thread..."
        cmake --build build --config Release
    }
    
    # Add to PATH
    echo 'export PATH="$HOME/llama.cpp/build/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/llama.cpp/build/bin:$PATH"
    
    echo "✓ llama.cpp built"
}

# Setup Python environment
setup_python() {
    print_step "Setting up Python environment..."
    
    cd "$PROJECT_DIR"
    
    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install orchestrator dependencies
    pip install --upgrade pip
    pip install -r orchestrator/requirements.txt
    pip install -r web-manager/requirements.txt
    
    echo "✓ Python environment ready"
}

# Create directories
setup_dirs() {
    print_step "Creating directories..."
    
    mkdir -p "$PROJECT_DIR/models"
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/config"
    
    echo "✓ Directories created"
}

# Copy configuration
copy_config() {
    print_step "Setting up configuration..."
    
    cd "$PROJECT_DIR"
    
    # Copy .env.example to .env if it doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env
        print_warning "Created .env file. Please edit it with your configuration."
    fi
    
    # Create initial runtime config
    mkdir -p config
    cat > config/runtime_config.json << EOF
{
  "mode": "consensus",
  "single_mode": {
    "active_worker": "worker-1",
    "fallback_enabled": true
  },
  "consensus_mode": {
    "worker_count": 3,
    "use_judge": true,
    "timeout_seconds": 120,
    "parallel_dispatch": true
  },
  "workers": [
    {"id": "worker-1", "model": "unsloth/Llama-3.1-8B-Instruct-GGUF", "port": 8101, "enabled": true},
    {"id": "worker-2", "model": "Qwen/Qwen2.5-7B-Instruct-GGUF", "port": 8102, "enabled": true},
    {"id": "worker-3", "model": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct-GGUF", "port": 8103, "enabled": true}
  ],
  "judge": {
    "model": "unsloth/Llama-3.1-8B-Instruct-GGUF",
    "port": 8200,
    "enabled": true
  }
}
EOF
    
    echo "✓ Configuration files created"
}

# Install systemd services
install_services() {
    print_step "Installing systemd services..."
    
    # Create services directory
    mkdir -p ~/.config/systemd/user
    
    # Orchestrator service
    cat > ~/.config/systemd/user/strix-orchestrator.service << EOF
[Unit]
Description=Strix Consensus Orchestrator
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python -m orchestrator.main
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

    # Web manager service
    cat > ~/.config/systemd/user/strix-web-manager.service << EOF
[Unit]
Description=Strix Web Manager
After=network.target strix-orchestrator.service

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python web-manager/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

    # Nginx service (for port 80)
    sudo apt install -y nginx
    
    sudo tee /etc/nginx/sites-available/strix-consensus << EOF
server {
    listen 80;
    server_name localhost;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
    
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_set_header Host \$host;
    }
}
EOF

    sudo ln -sf /etc/nginx/sites-available/strix-consensus /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Check if systemd is available
    if pidof systemd > /dev/null 2>&1; then
        print_step "Reloading systemd..."
        systemctl --user daemon-reload 2>/dev/null || true
        sudo systemctl daemon-reload 2>/dev/null || true
        echo "✓ Services installed (systemd mode)"
    else
        print_warning "Systemd not available, services will be managed manually"
        echo "✓ Services installed (manual mode)"
    fi
}

# Main installation
main() {
    echo "=========================================="
    echo "Strix Consensus Server Installer"
    echo "=========================================="
    echo ""
    
    # Check if in correct directory
    if [ ! -f "docker-compose.yml" ]; then
        print_error "Please run this script from the strix-consensus-server directory"
        exit 1
    fi
    
    # Set project directory
    PROJECT_DIR="$(pwd)"
    
    check_wsl
    update_system
    install_deps
    install_rocm
    build_llama_cpp
    setup_dirs
    copy_config
    setup_python
    install_services
    
    echo ""
    echo "=========================================="
    echo -e "${GREEN}Installation Complete!${NC}"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your configuration"
    echo "2. Run: ./scripts/start-all.sh"
    echo "3. Access web interface at http://localhost"
    echo ""
    
    # Check if systemd is available for final message
    if pidof systemd > /dev/null 2>&1; then
        echo "To start services on boot:"
        echo "  systemctl --user enable strix-orchestrator"
        echo "  systemctl --user enable strix-web-manager"
        echo ""
    else
        echo "Note: Systemd not detected. Services will run in foreground."
        echo "To run in background, use: nohup ./scripts/start-all.sh &"
        echo ""
    fi
}

# Run installation
main "$@"
