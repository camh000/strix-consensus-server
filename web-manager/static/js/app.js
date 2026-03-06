// Strix Consensus Server - Web Interface JavaScript

let currentStatus = null;
let refreshInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
    setupEventListeners();
    startAutoRefresh();
});

function initDashboard() {
    loadStatus();
    loadWorkers();
    loadLogs();
    loadAvailableModels();
}

function setupEventListeners() {
    // Mode selection
    document.querySelectorAll('input[name="mode"]').forEach(radio => {
        radio.addEventListener('change', handleModeChange);
    });
    
    // Apply mode button
    document.getElementById('apply-mode-btn').addEventListener('click', applyMode);
    
    // Worker count slider
    const workerSlider = document.getElementById('worker-count');
    const workerDisplay = document.getElementById('worker-count-display');
    workerSlider.addEventListener('input', (e) => {
        workerDisplay.textContent = e.target.value;
    });
    
    // Refresh logs
    document.getElementById('refresh-logs-btn').addEventListener('click', loadLogs);
    
    // Logs limit
    document.getElementById('logs-limit').addEventListener('change', loadLogs);
    
    // Model tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    
    // Model search
    document.getElementById('search-btn').addEventListener('click', searchModels);
    document.getElementById('model-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchModels();
    });
    
    // File upload
    setupFileUpload();
}

function startAutoRefresh() {
    // Refresh status every 5 seconds
    refreshInterval = setInterval(() => {
        loadStatus();
    }, 5000);
}

// API Functions
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        currentStatus = data;
        
        updateConnectionStatus(true);
        updateModeDisplay(data.config);
        updateStats(data.stats);
        updateWorkerSelect(data.config.workers);
    } catch (error) {
        console.error('Failed to load status:', error);
        updateConnectionStatus(false);
    }
}

async function loadWorkers() {
    try {
        const response = await fetch('/api/workers');
        const workers = await response.json();
        renderWorkers(workers);
    } catch (error) {
        console.error('Failed to load workers:', error);
    }
}

async function loadLogs() {
    try {
        const limit = document.getElementById('logs-limit').value;
        const response = await fetch(`/api/logs?limit=${limit}`);
        const data = await response.json();
        renderLogs(data.logs);
    } catch (error) {
        console.error('Failed to load logs:', error);
    }
}

async function loadAvailableModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();
        renderAvailableModels(data.models);
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function applyMode() {
    const mode = document.querySelector('input[name="mode"]:checked')?.value;
    if (!mode) {
        alert('Please select a mode');
        return;
    }
    
    const config = { mode };
    
    if (mode === 'single') {
        config.active_worker = document.getElementById('active-worker-select').value;
    } else {
        config.worker_count = parseInt(document.getElementById('worker-count').value);
        config.use_judge = document.getElementById('use-judge').checked;
    }
    
    try {
        const response = await fetch('/api/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification('Mode updated successfully', 'success');
            loadStatus();
        } else {
            showNotification('Failed to update mode: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// UI Update Functions
function updateConnectionStatus(connected) {
    const indicator = document.querySelector('.status-dot');
    const statusText = document.getElementById('connection-status');
    
    if (connected) {
        indicator.classList.add('online');
        statusText.textContent = 'Connected';
    } else {
        indicator.classList.remove('online');
        statusText.textContent = 'Disconnected';
    }
}

function updateModeDisplay(config) {
    if (!config) return;
    
    const mode = config.mode;
    document.getElementById(`mode-${mode}`).checked = true;
    
    if (mode === 'single') {
        document.getElementById('active-worker-select').value = config.single_mode?.active_worker || '';
    } else {
        document.getElementById('worker-count').value = config.consensus_mode?.worker_count || 3;
        document.getElementById('worker-count-display').textContent = config.consensus_mode?.worker_count || 3;
        document.getElementById('use-judge').checked = config.consensus_mode?.use_judge !== false;
    }
}

function updateStats(stats) {
    document.getElementById('stat-total').textContent = stats?.total_requests || 0;
    document.getElementById('stat-consensus').textContent = stats?.consensus_requests || 0;
    document.getElementById('stat-latency').textContent = 
        (stats?.avg_latency || 0).toFixed(2) + 's';
}

function updateWorkerSelect(workers) {
    const select = document.getElementById('active-worker-select');
    const currentValue = select.value;
    
    select.innerHTML = workers.map(w => 
        `<option value="${w.id}">${w.id} (${w.model.split('/').pop()})</option>`
    ).join('');
    
    if (currentValue) {
        select.value = currentValue;
    }
}

function renderWorkers(workers) {
    const container = document.getElementById('worker-list');
    
    if (!workers || workers.length === 0) {
        container.innerHTML = '<p>No workers configured</p>';
        return;
    }
    
    container.innerHTML = workers.map(worker => `
        <div class="worker-item">
            <div class="worker-info">
                <h4>${worker.id}</h4>
                <p>${worker.model}</p>
                <small>Port: ${worker.port}</small>
            </div>
            <div class="worker-status">
                <span class="status-badge ${worker.enabled ? 'online' : 'offline'}">
                    ${worker.enabled ? 'Enabled' : 'Disabled'}
                </span>
            </div>
        </div>
    `).join('');
}

function renderLogs(logs) {
    const container = document.getElementById('consensus-logs');
    
    if (!logs || logs.length === 0) {
        container.innerHTML = '<p>No consensus decisions yet</p>';
        return;
    }
    
    container.innerHTML = logs.map(log => `
        <div class="log-entry">
            <div class="timestamp">${new Date(log.timestamp).toLocaleString()}</div>
            <div class="prompt">${truncate(log.prompt, 100)}</div>
            <div class="winner">Winner: ${log.winner}</div>
            <div class="reasoning">${log.reasoning}</div>
        </div>
    `).join('');
}

function renderAvailableModels(models) {
    const container = document.getElementById('available-models');
    
    container.innerHTML = models.map(model => `
        <div class="model-card">
            <h4>${model.name}</h4>
            <div class="size">${model.size}</div>
            <p class="description">${model.description}</p>
            <button class="btn btn-primary" onclick="downloadModel('${model.id}')">
                Download
            </button>
        </div>
    `).join('');
}

// Event Handlers
function handleModeChange(e) {
    const mode = e.target.value;
    
    // Update UI based on mode
    document.querySelectorAll('.mode-details').forEach(el => {
        el.style.opacity = '0.5';
    });
    
    e.target.closest('.mode-option').querySelector('.mode-details').style.opacity = '1';
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(`${tabId}-tab`).classList.add('active');
}

function searchModels() {
    const query = document.getElementById('model-search').value.toLowerCase();
    const cards = document.querySelectorAll('.model-card');
    
    cards.forEach(card => {
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? 'block' : 'none';
    });
}

async function downloadModel(modelId) {
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: modelId })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`Download queued for ${modelId}`, 'success');
        } else {
            showNotification('Failed to queue download', 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// File Upload
function setupFileUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const progressDiv = document.getElementById('upload-progress');
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
    
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
    
    async function handleFiles(files) {
        for (const file of files) {
            if (!file.name.endsWith('.gguf')) {
                showNotification(`Skipping ${file.name}: Not a .gguf file`, 'warning');
                continue;
            }
            
            await uploadFile(file);
        }
    }
    
    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        progressDiv.innerHTML = `<p>Uploading ${file.name}...</p>`;
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showNotification(`Uploaded ${file.name} successfully`, 'success');
                progressDiv.innerHTML = '';
            } else {
                showNotification(`Failed to upload ${file.name}: ${result.error}`, 'error');
            }
        } catch (error) {
            showNotification(`Error uploading ${file.name}: ${error.message}`, 'error');
        }
    }
}

// Utilities
function truncate(str, maxLength) {
    if (!str) return '';
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength) + '...';
}

function showNotification(message, type = 'info') {
    // Simple notification - could be enhanced
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // You could add a toast notification system here
    alert(`${type.toUpperCase()}: ${message}`);
}
