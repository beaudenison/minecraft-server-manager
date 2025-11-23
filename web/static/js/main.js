let consoleUpdateInterval;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updateStatus();
    loadProperties();
    loadWorlds();
    
    // Update console every 2 seconds when on console tab
    setInterval(() => {
        if (document.getElementById('console-tab').classList.contains('active')) {
            updateConsole();
        }
    }, 2000);
    
    // Update status every 5 seconds
    setInterval(updateStatus, 5000);
});

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName + '-tab').classList.add('active');
    event.target.classList.add('active');
    
    // Load data for specific tabs
    if (tabName === 'config') {
        loadProperties();
    } else if (tabName === 'worlds') {
        loadWorlds();
    } else if (tabName === 'console') {
        updateConsole();
    }
}

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        const statusBadge = document.getElementById('server-status');
        if (data.status === 'running') {
            statusBadge.textContent = 'Running';
            statusBadge.className = 'status-badge status-running';
        } else {
            statusBadge.textContent = 'Stopped';
            statusBadge.className = 'status-badge status-stopped';
        }
        
        // Update worlds list if on worlds tab
        if (document.getElementById('worlds-tab').classList.contains('active')) {
            displayWorlds(data.worlds, data.active_world);
        }
    } catch (error) {
        console.error('Failed to update status:', error);
    }
}

async function startServer() {
    showNotification('Starting server...', 'success');
    try {
        const response = await fetch('/api/start', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showNotification(data.message, 'success');
            setTimeout(updateStatus, 1000);
            updateConsole();
        } else {
            showNotification(data.message, 'error');
        }
    } catch (error) {
        showNotification('Failed to start server', 'error');
    }
}

async function stopServer() {
    showNotification('Stopping server...', 'success');
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        
        showNotification(data.message, data.success ? 'success' : 'error');
        setTimeout(updateStatus, 1000);
    } catch (error) {
        showNotification('Failed to stop server', 'error');
    }
}

async function restartServer() {
    showNotification('Restarting server...', 'success');
    try {
        const response = await fetch('/api/restart', { method: 'POST' });
        const data = await response.json();
        
        showNotification(data.message, data.success ? 'success' : 'error');
        setTimeout(updateStatus, 2000);
        updateConsole();
    } catch (error) {
        showNotification('Failed to restart server', 'error');
    }
}

async function updateConsole() {
    try {
        const response = await fetch('/api/console');
        const data = await response.json();
        
        const consoleOutput = document.getElementById('console-output');
        consoleOutput.textContent = data.output.join('\n');
        
        // Auto-scroll to bottom
        const container = consoleOutput.parentElement;
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Failed to update console:', error);
    }
}

async function sendCommand() {
    const input = document.getElementById('command-input');
    const command = input.value.trim();
    
    if (!command) return;
    
    try {
        const response = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const data = await response.json();
        
        if (data.success) {
            input.value = '';
            setTimeout(updateConsole, 500);
        } else {
            showNotification(data.message, 'error');
        }
    } catch (error) {
        showNotification('Failed to send command', 'error');
    }
}

function handleCommandKey(event) {
    if (event.key === 'Enter') {
        sendCommand();
    }
}

async function uploadJar() {
    const fileInput = document.getElementById('jar-file');
    const file = fileInput.files[0];
    const statusDiv = document.getElementById('jar-status');
    
    if (!file) {
        statusDiv.textContent = 'Please select a file';
        statusDiv.className = 'upload-status error';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    statusDiv.textContent = 'Uploading...';
    statusDiv.className = 'upload-status';
    statusDiv.style.display = 'block';
    
    try {
        const response = await fetch('/api/upload-jar', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        statusDiv.textContent = data.message;
        statusDiv.className = data.success ? 'upload-status success' : 'upload-status error';
        
        if (data.success) {
            fileInput.value = '';
            showNotification(data.message, 'success');
            updateStatus();
        }
    } catch (error) {
        statusDiv.textContent = 'Upload failed';
        statusDiv.className = 'upload-status error';
    }
}

async function uploadWorld() {
    const fileInput = document.getElementById('world-file');
    const file = fileInput.files[0];
    const statusDiv = document.getElementById('world-status');
    
    if (!file) {
        statusDiv.textContent = 'Please select a file';
        statusDiv.className = 'upload-status error';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    statusDiv.textContent = 'Uploading...';
    statusDiv.className = 'upload-status';
    statusDiv.style.display = 'block';
    
    try {
        const response = await fetch('/api/upload-world', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        statusDiv.textContent = data.message;
        statusDiv.className = data.success ? 'upload-status success' : 'upload-status error';
        
        if (data.success) {
            fileInput.value = '';
            showNotification(data.message, 'success');
            loadWorlds();
        }
    } catch (error) {
        statusDiv.textContent = 'Upload failed';
        statusDiv.className = 'upload-status error';
    }
}

async function loadWorlds() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        displayWorlds(data.worlds, data.active_world);
    } catch (error) {
        console.error('Failed to load worlds:', error);
    }
}

function displayWorlds(worlds, activeWorld) {
    const worldsList = document.getElementById('worlds-list');
    
    if (!worlds || worlds.length === 0) {
        worldsList.innerHTML = '<p>No worlds uploaded yet</p>';
        return;
    }
    
    worldsList.innerHTML = worlds.map(world => `
        <div class="world-item ${world === activeWorld ? 'active' : ''}">
            <div>
                <strong>${world}</strong>
                ${world === activeWorld ? ' <span style="color: #27ae60;">● Active</span>' : ''}
            </div>
            <button class="btn btn-primary" onclick="setActiveWorld('${world}')" 
                    ${world === activeWorld ? 'disabled' : ''}>
                Set Active
            </button>
        </div>
    `).join('');
}

async function setActiveWorld(worldName) {
    try {
        const response = await fetch('/api/set-world', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ world: worldName })
        });
        const data = await response.json();
        
        showNotification(data.message, data.success ? 'success' : 'error');
        
        if (data.success) {
            loadWorlds();
        }
    } catch (error) {
        showNotification('Failed to set active world', 'error');
    }
}

async function loadProperties() {
    try {
        const response = await fetch('/api/properties');
        const data = await response.json();
        
        const editor = document.getElementById('properties-editor');
        if (data.success) {
            editor.value = data.content;
        } else {
            editor.value = '# server.properties will be created when server first starts';
        }
    } catch (error) {
        console.error('Failed to load properties:', error);
    }
}

async function saveProperties() {
    const content = document.getElementById('properties-editor').value;
    const statusDiv = document.getElementById('properties-status');
    
    try {
        const response = await fetch('/api/properties', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        const data = await response.json();
        
        statusDiv.textContent = data.message;
        statusDiv.className = data.success ? 'upload-status success' : 'upload-status error';
        
        showNotification(data.message, data.success ? 'success' : 'error');
    } catch (error) {
        statusDiv.textContent = 'Failed to save properties';
        statusDiv.className = 'upload-status error';
    }
}

function showNotification(message, type) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 4000);
}