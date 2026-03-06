# Web Manager for Strix Consensus Server
# Port 80 management interface

from flask import Flask, render_template, jsonify, request, flash, redirect
import os
import json
import requests
import threading
import time
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Get orchestrator URL from environment, try to auto-detect if not set
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL')
if not ORCHESTRATOR_URL:
    # Try to detect the IP address
    import socket
    try:
        # Get the IP address used to connect to the internet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        ORCHESTRATOR_URL = f"http://{ip}:8080"
    except:
        ORCHESTRATOR_URL = "http://localhost:8080"

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """Get system status from orchestrator"""
    try:
        response = requests.get(f"{ORCHESTRATOR_URL}/api/status", timeout=5)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({
            "error": str(e),
            "mode": "unknown",
            "workers": {},
            "stats": {}
        }), 503

@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Change operating mode"""
    data = request.json
    
    try:
        response = requests.post(
            f"{ORCHESTRATOR_URL}/api/mode",
            json=data,
            timeout=5
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Get consensus logs"""
    try:
        limit = request.args.get('limit', 100, type=int)
        response = requests.get(
            f"{ORCHESTRATOR_URL}/api/logs?limit={limit}",
            timeout=5
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"logs": [], "error": str(e)})

@app.route('/api/models')
def list_models():
    """List available models from HuggingFace"""
    # This could query a local database or fetch from HF API
    models = [
        {
            "id": "unsloth/Llama-3.1-8B-Instruct-GGUF",
            "name": "Llama 3.1 8B Instruct",
            "size": "4.5GB (Q4_K_M)",
            "description": "Meta's Llama 3.1 8B instruction-tuned model"
        },
        {
            "id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
            "name": "Qwen 2.5 7B Instruct",
            "size": "4.5GB (Q4_K_M)",
            "description": "Alibaba's Qwen 2.5 7B instruction-tuned"
        },
        {
            "id": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct-GGUF",
            "name": "DeepSeek Coder V2 Lite",
            "size": "5GB (Q4_K_M)",
            "description": "Specialized for coding tasks"
        },
        {
            "id": "microsoft/Phi-3-mini-4k-instruct-GGUF",
            "name": "Phi-3 Mini 4K",
            "size": "2GB (Q4_K_M)",
            "description": "Microsoft's small but capable model"
        },
        {
            "id": "google/gemma-2-2b-it-GGUF",
            "name": "Gemma 2 2B IT",
            "size": "1.5GB (Q4_K_M)",
            "description": "Google's efficient small model"
        }
    ]
    return jsonify({"models": models})

@app.route('/api/upload', methods=['POST'])
def upload_model():
    """Upload a GGUF file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith('.gguf'):
        return jsonify({"error": "Only .gguf files allowed"}), 400
    
    # Save file
    models_dir = os.getenv('MODELS_DIR', './models')
    os.makedirs(models_dir, exist_ok=True)
    
    filepath = os.path.join(models_dir, file.filename)
    file.save(filepath)
    
    return jsonify({
        "status": "success",
        "filename": file.filename,
        "path": filepath
    })

@app.route('/api/workers', methods=['GET'])
def get_workers():
    """Get worker configuration"""
    try:
        response = requests.get(f"{ORCHESTRATOR_URL}/api/status", timeout=5)
        data = response.json()
        return jsonify(data.get('config', {}).get('workers', []))
    except Exception as e:
        return jsonify([])

@app.route('/api/workers/<worker_id>/enable', methods=['POST'])
def enable_worker(worker_id):
    """Enable a worker"""
    # This would update the orchestrator config
    return jsonify({"status": "success", "action": "enable", "worker_id": worker_id})

@app.route('/api/workers/<worker_id>/disable', methods=['POST'])
def disable_worker(worker_id):
    """Disable a worker"""
    return jsonify({"status": "success", "action": "disable", "worker_id": worker_id})

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        response = requests.get(f"{ORCHESTRATOR_URL}/api/status", timeout=5)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config/models', methods=['POST'])
def update_model_config():
    """Update worker and judge model configuration"""
    data = request.json
    
    try:
        # Forward to orchestrator
        response = requests.post(
            f"{ORCHESTRATOR_URL}/api/config/models",
            json=data,
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        # If orchestrator doesn't support this yet, save locally
        try:
            config_file = '../config/runtime_config.json'
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Update worker models
            if 'workers' in data:
                for worker_update in data['workers']:
                    for worker in config.get('workers', []):
                        if worker['id'] == worker_update['id']:
                            worker['model'] = worker_update['model']
                            break
            
            # Update judge model
            if 'judge' in data and config.get('judge'):
                config['judge']['model'] = data['judge']['model']
            
            # Save config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return jsonify({
                "status": "success",
                "message": "Configuration saved. Please restart services to apply changes."
            })
        except Exception as config_error:
            return jsonify({
                "error": f"Failed to update configuration: {str(config_error)}"
            }), 500

@app.route('/api/models/reload', methods=['POST'])
def reload_models():
    """Reload all models with new configuration"""
    try:
        # Forward to orchestrator
        response = requests.post(
            f"{ORCHESTRATOR_URL}/api/models/reload",
            timeout=5
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        # If orchestrator doesn't support this, return manual instructions
        return jsonify({
            "status": "info",
            "message": "To reload models, please run: ./scripts/restart-orchestrator.sh"
        })

# In-memory download tracking (would be better with a database or Redis)
downloads_store = {
    'active': [],
    'completed': []
}

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Shutdown all services"""
    try:
        import subprocess
        import time
        
        # Stop nginx
        subprocess.run(['sudo', 'pkill', 'nginx'], capture_output=True)
        
        # Kill orchestrator
        subprocess.run(['pkill', '-f', 'orchestrator.main'], capture_output=True)
        
        # Kill web-manager (this process)
        threading.Thread(target=lambda: (
            time.sleep(1),
            os._exit(0)
        )).start()
        
        return jsonify({
            "status": "success",
            "message": "All services are shutting down..."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/downloads')
def get_downloads():
    """Get active and completed downloads"""
    return jsonify(downloads_store)

@app.route('/api/downloads/clear', methods=['POST'])
def clear_downloads():
    """Clear completed downloads"""
    downloads_store['completed'] = []
    return jsonify({"status": "success"})

@app.route('/api/download', methods=['POST'])
def download_model():
    """Download a model with tracking"""
    data = request.json
    model_id = data.get('model_id')
    
    if not model_id:
        return jsonify({"error": "No model_id provided"}), 400
    
    # Create download entry
    download_id = str(int(time.time()))
    download_entry = {
        'id': download_id,
        'model_id': model_id,
        'name': model_id.split('/')[-1] if '/' in model_id else model_id,
        'progress': 0.0,
        'downloaded': 0,
        'total': 0,
        'speed': '',
        'eta': 'Calculating...',
        'status': 'downloading',
        'started_at': datetime.now().isoformat()
    }
    
    downloads_store['active'].append(download_entry)
    print(f"[DOWNLOAD] Added download to store: {download_entry['id']} - {model_id}")
    print(f"[DOWNLOAD] Current active downloads: {len(downloads_store['active'])}")
    
    # Start download in background thread
    def download_worker():
        print(f"[DOWNLOAD WORKER] Starting download for {model_id}")
        try:
            # Call the actual download logic
            import urllib.request
            import os
            
            models_dir = os.getenv('MODELS_DIR', './models')
            print(f"[DOWNLOAD WORKER] Models dir: {models_dir}")
            os.makedirs(models_dir, exist_ok=True)
            
            # Get filename from model_id
            parts = model_id.split('/')
            if len(parts) >= 2:
                filename = f"{parts[-1]}.gguf"
            else:
                filename = f"{model_id}.gguf"
            
            filepath = os.path.join(models_dir, filename)
            print(f"[DOWNLOAD WORKER] Will save to: {filepath}")
            
            # Download with progress tracking
            def download_progress_hook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                
                download_entry['downloaded'] = downloaded
                download_entry['total'] = total_size
                download_entry['progress'] = progress
                
                # Update in store
                for i, d in enumerate(downloads_store['active']):
                    if d['id'] == download_id:
                        downloads_store['active'][i] = download_entry
                        break
            
            # Attempt download from HuggingFace
            url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"
            print(f"[DOWNLOAD WORKER] Downloading from: {url}")
            urllib.request.urlretrieve(url, filepath, download_progress_hook)
            print(f"[DOWNLOAD WORKER] Download completed successfully")
            
            # Mark as completed
            download_entry['progress'] = 100.0
            download_entry['completed_at'] = datetime.now().isoformat()
            download_entry['status'] = 'completed'
            
            # Move to completed
            downloads_store['active'] = [d for d in downloads_store['active'] if d['id'] != download_id]
            downloads_store['completed'].insert(0, download_entry)
            print(f"[DOWNLOAD WORKER] Moved to completed. Total completed: {len(downloads_store['completed'])}")
            
        except Exception as e:
            print(f"[DOWNLOAD WORKER] ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            download_entry['status'] = 'failed'
            download_entry['error'] = str(e)
            downloads_store['active'] = [d for d in downloads_store['active'] if d['id'] != download_id]
    
    threading.Thread(target=download_worker, daemon=True).start()
    
    return jsonify({
        "status": "queued",
        "download_id": download_id,
        "message": f"Download started for {model_id}"
    })

if __name__ == '__main__':
    port = int(os.getenv('WEB_MANAGER_PORT', 5000))
    # Note: In production, use nginx to forward port 80 to this
    app.run(host='0.0.0.0', port=port, debug=False)
