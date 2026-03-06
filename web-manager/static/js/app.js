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
    loadModelConfiguration();
    startDownloadsRefresh();
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
    
    // Model configuration
    document.getElementById('save-model-config-btn')?.addEventListener('click', saveModelConfiguration);
    document.getElementById('reload-models-btn')?.addEventListener('click', reloadModels);
    
    // Shutdown handlers
    setupShutdownHandlers();
    
    // Downloads handlers
    document.getElementById('refresh-downloads-btn')?.addEventListener('click', loadDownloads);
    document.getElementById('clear-completed-btn')?.addEventListener('click', clearCompletedDownloads);
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
        window.availableModels = data.models; // Store for model config
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

// Model Configuration Functions
async function loadModelConfiguration() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        renderModelConfiguration(data.config);
    } catch (error) {
        console.error('Failed to load model configuration:', error);
    }
}

function renderModelConfiguration(config) {
    const container = document.getElementById('worker-model-config');
    if (!container) return;
    
    if (!config || !config.workers) {
        container.innerHTML = '<p>No configuration available</p>';
        return;
    }
    
    const models = window.availableModels || [];
    const modelOptions = models.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
    
    let html = '';
    
    // Render workers
    config.workers.forEach(worker => {
        html += `
            <div class="model-config-item worker" data-worker-id="${worker.id}">
                <span class="role-badge">Worker</span>
                <div class="config-info">
                    <h4>${worker.id}</h4>
                    <p>Port: ${worker.port}</p>
                </div>
                <select class="model-select" data-worker-id="${worker.id}">
                    <option value="">Select a model...</option>
                    ${modelOptions}
                    <option value="custom" ${!models.find(m => m.id === worker.model) ? 'selected' : ''}>${worker.model}</option>
                </select>
            </div>
        `;
    });
    
    // Render judge
    if (config.judge) {
        html += `
            <div class="model-config-item judge" data-worker-id="judge">
                <span class="role-badge">Judge</span>
                <div class="config-info">
                    <h4>Judge Model</h4>
                    <p>Port: ${config.judge.port}</p>
                </div>
                <select class="model-select" data-worker-id="judge">
                    <option value="">Select a model...</option>
                    ${modelOptions}
                    <option value="custom" ${!models.find(m => m.id === config.judge.model) ? 'selected' : ''}>${config.judge.model}</option>
                </select>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // Set current values
    config.workers.forEach(worker => {
        const select = container.querySelector(`select[data-worker-id="${worker.id}"]`);
        if (select) {
            // Check if the model is in the available models list
            const optionExists = Array.from(select.options).some(opt => opt.value === worker.model);
            if (optionExists) {
                select.value = worker.model;
            }
        }
    });
    
    if (config.judge) {
        const judgeSelect = container.querySelector('select[data-worker-id="judge"]');
        if (judgeSelect) {
            const optionExists = Array.from(judgeSelect.options).some(opt => opt.value === config.judge.model);
            if (optionExists) {
                judgeSelect.value = config.judge.model;
            }
        }
    }
}

async function saveModelConfiguration() {
    const container = document.getElementById('worker-model-config');
    if (!container) return;
    
    const config = {
        workers: [],
        judge: null
    };
    
    // Collect worker configurations
    container.querySelectorAll('.model-config-item.worker').forEach(item => {
        const workerId = item.dataset.workerId;
        const select = item.querySelector('.model-select');
        const modelId = select.value;
        
        if (modelId && modelId !== 'custom') {
            config.workers.push({
                id: workerId,
                model: modelId
            });
        }
    });
    
    // Collect judge configuration
    const judgeItem = container.querySelector('.model-config-item.judge');
    if (judgeItem) {
        const select = judgeItem.querySelector('.model-select');
        const modelId = select.value;
        
        if (modelId && modelId !== 'custom') {
            config.judge = {
                model: modelId
            };
        }
    }
    
    try {
        const response = await fetch('/api/config/models', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification('Model configuration saved successfully', 'success');
            showNotification('Models will be reloaded automatically', 'info');
        } else {
            showNotification('Failed to save configuration: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error saving configuration: ' + error.message, 'error');
    }
}

async function reloadModels() {
    try {
        const response = await fetch('/api/models/reload', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification('Models reloading... This may take a few minutes', 'success');
            // Refresh status after a delay
            setTimeout(() => {
                loadStatus();
                loadModelConfiguration();
            }, 5000);
        } else {
            showNotification('Failed to reload models: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error reloading models: ' + error.message, 'error');
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

// Shutdown Functions
function setupShutdownHandlers() {
    const shutdownBtn = document.getElementById('shutdown-btn');
    const shutdownDialog = document.getElementById('shutdown-dialog');
    const confirmBtn = document.getElementById('confirm-shutdown-btn');
    const cancelBtn = document.getElementById('cancel-shutdown-btn');
    
    if (shutdownBtn) {
        shutdownBtn.addEventListener('click', () => {
            shutdownDialog.classList.add('active');
        });
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            shutdownDialog.classList.remove('active');
        });
    }
    
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            shutdownDialog.classList.remove('active');
            await performShutdown();
        });
    }
    
    // Close modal when clicking outside
    if (shutdownDialog) {
        shutdownDialog.addEventListener('click', (e) => {
            if (e.target === shutdownDialog) {
                shutdownDialog.classList.remove('active');
            }
        });
    }
}

async function performShutdown() {
    showNotification('Shutting down services...', 'info');
    
    try {
        const response = await fetch('/api/shutdown', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification('Services shutting down...', 'success');
            // Show shutdown message
            document.body.innerHTML = `
                <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #0f172a; color: #f1f5f9; text-align: center;">
                    <div>
                        <h1>⏻ System Shutdown</h1>
                        <p>All services have been stopped.</p>
                        <p style="color: #94a3b8; margin-top: 20px;">${result.message}</p>
                    </div>
                </div>
            `;
        } else {
            showNotification('Shutdown failed: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error during shutdown: ' + error.message, 'error');
    }
}

// Downloads Functions
let downloadsRefreshInterval = null;

function startDownloadsRefresh() {
    // Refresh downloads every 3 seconds
    loadDownloads();
    downloadsRefreshInterval = setInterval(loadDownloads, 3000);
}

function stopDownloadsRefresh() {
    if (downloadsRefreshInterval) {
        clearInterval(downloadsRefreshInterval);
        downloadsRefreshInterval = null;
    }
}

async function loadDownloads() {
    try {
        const response = await fetch('/api/downloads');
        const data = await response.json();
        renderDownloads(data);
    } catch (error) {
        console.error('Failed to load downloads:', error);
    }
}

function renderDownloads(data) {
    const activeContainer = document.getElementById('active-downloads');
    const completedContainer = document.getElementById('completed-downloads');
    
    if (!activeContainer || !completedContainer) return;
    
    const active = data.active || [];
    const completed = data.completed || [];
    
    // Render active downloads
    if (active.length === 0) {
        activeContainer.innerHTML = '<p class="no-downloads">No active downloads</p>';
    } else {
        activeContainer.innerHTML = active.map(download => `
            <div class="download-item downloading" data-download-id="${download.id}">
                <div class="download-info">
                    <h4>${download.name}</h4>
                    <div class="download-status">
                        <span class="status-badge downloading">Downloading</span>
                        <span>${download.speed || ''}</span>
                    </div>
                </div>
                <div class="download-details">
                    <span>${formatBytes(download.downloaded)} / ${formatBytes(download.total)}</span>
                    <span>ETA: ${download.eta || 'Calculating...'}</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${download.progress}%"></div>
                </div>
                <div class="download-percentage">${download.progress.toFixed(1)}%</div>
            </div>
        `).join('');
    }
    
    // Render completed downloads
    if (completed.length === 0) {
        completedContainer.innerHTML = '<p class="no-downloads">No completed downloads yet</p>';
    } else {
        completedContainer.innerHTML = completed.map(download => `
            <div class="download-item completed" data-download-id="${download.id}">
                <div class="download-info">
                    <h4>${download.name}</h4>
                    <div class="download-status">
                        <span class="status-badge completed">Complete</span>
                    </div>
                </div>
                <div class="download-details">
                    <span>${formatBytes(download.total)}</span>
                    <span>Completed: ${new Date(download.completed_at).toLocaleString()}</span>
                </div>
            </div>
        `).join('');
    }
    
    // Update available models dropdown if new models were downloaded
    if (completed.length > 0 && window.availableModels) {
        updateAvailableModelsWithDownloads(completed);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function updateAvailableModelsWithDownloads(completedDownloads) {
    // Add completed downloads to available models if not already present
    completedDownloads.forEach(download => {
        const exists = window.availableModels.some(m => m.id === download.model_id);
        if (!exists) {
            window.availableModels.push({
                id: download.model_id,
                name: download.name,
                size: formatBytes(download.total),
                description: 'Downloaded model'
            });
        }
    });
}

async function clearCompletedDownloads() {
    try {
        const response = await fetch('/api/downloads/clear', {
            method: 'POST'
        });
        
        if (response.ok) {
            loadDownloads();
            showNotification('Completed downloads cleared', 'success');
        }
    } catch (error) {
        showNotification('Error clearing downloads: ' + error.message, 'error');
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
