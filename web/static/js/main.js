let consoleUpdateInterval;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updateStatus();
    updateHealth();
    loadProperties();
    loadWorlds();
    loadCurrentUsername();
    
    // Update console every 2 seconds when on console tab
    setInterval(() => {
        if (document.getElementById('console-tab').classList.contains('active')) {
            updateConsole();
            updateHealth();
        }
    }, 2000);
    
    // Update status every 5 seconds
    setInterval(updateStatus, 5000);
});

async function loadCurrentUsername() {
    try {
        const response = await fetch('/api/users');
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        if (data.success) {
            const usernameEl = document.getElementById('current-username');
            if (usernameEl) {
                usernameEl.textContent = data.current_user;
            }
        }
    } catch (error) {
        console.error('Failed to load username:', error);
    }
}

async function logout() {
    try {
        const response = await fetch('/logout', { method: 'POST' });
        if (response.ok) {
            window.location.href = '/';
        }
    } catch (error) {
        console.error('Logout failed:', error);
    }
}

async function handleApiError(response) {
    if (response.status === 401) {
        window.location.href = '/';
        return true;
    }
    return false;
}

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
        updateHealth();
    } else if (tabName === 'users') {
        loadUsers();
    } else if (tabName === 'backups') {
        loadBackups();
    }
}

async function updateHealth() {
    try {
        const response = await fetch('/api/health');
        if (await handleApiError(response)) return;
        
        const data = await response.json();
        
        if (data.success && data.health) {
            const health = data.health;
            
            // Update health display
            document.getElementById('cpu-usage').textContent = health.cpu_percent.toFixed(1) + '%';
            document.getElementById('memory-usage').textContent = Math.round(health.memory_mb) + ' MB';
            
            // Format uptime
            const uptime = health.uptime_seconds;
            let uptimeStr = '0s';
            if (uptime > 0) {
                const hours = Math.floor(uptime / 3600);
                const minutes = Math.floor((uptime % 3600) / 60);
                const seconds = uptime % 60;
                
                if (hours > 0) {
                    uptimeStr = `${hours}h ${minutes}m`;
                } else if (minutes > 0) {
                    uptimeStr = `${minutes}m ${seconds}s`;
                } else {
                    uptimeStr = `${seconds}s`;
                }
            }
            document.getElementById('uptime').textContent = uptimeStr;
            
            // Show/hide health bar based on server status
            const healthBar = document.getElementById('server-health');
            if (health.status === 'running') {
                healthBar.style.display = 'flex';
            } else {
                healthBar.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to update health:', error);
    }
}

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        if (await handleApiError(response)) return;
        
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

// Backup Functions
async function createBackup() {
    const statusDiv = document.getElementById('backup-status');
    statusDiv.textContent = 'Creating backup...';
    statusDiv.className = 'upload-status';
    statusDiv.style.display = 'block';
    
    try {
        const response = await fetch('/api/backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        statusDiv.textContent = data.message;
        statusDiv.className = data.success ? 'upload-status success' : 'upload-status error';
        
        if (data.success) {
            showNotification(data.message, 'success');
            loadBackups();
        }
    } catch (error) {
        statusDiv.textContent = 'Failed to create backup';
        statusDiv.className = 'upload-status error';
    }
}

async function loadBackups() {
    try {
        const response = await fetch('/api/backups');
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        const backupsList = document.getElementById('backups-list');
        
        if (!data.success || !data.backups || data.backups.length === 0) {
            backupsList.innerHTML = '<p>No backups found</p>';
            return;
        }
        
        backupsList.innerHTML = data.backups.map(backup => `
            <div class="backup-item">
                <div class="backup-info">
                    <strong>${backup.name}</strong>
                    <small>Size: ${backup.size_mb} MB | Created: ${backup.created}</small>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load backups:', error);
        document.getElementById('backups-list').innerHTML = '<p>Error loading backups</p>';
    }
}

// User Management Functions
async function changePassword() {
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const statusDiv = document.getElementById('password-status');
    
    if (!currentPassword || !newPassword) {
        statusDiv.textContent = 'Please fill in all fields';
        statusDiv.className = 'upload-status error';
        return;
    }
    
    if (newPassword.length < 6) {
        statusDiv.textContent = 'New password must be at least 6 characters';
        statusDiv.className = 'upload-status error';
        return;
    }
    
    try {
        const response = await fetch('/api/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
        });
        
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        statusDiv.textContent = data.message;
        statusDiv.className = data.success ? 'upload-status success' : 'upload-status error';
        
        if (data.success) {
            document.getElementById('current-password').value = '';
            document.getElementById('new-password').value = '';
            showNotification('Password changed successfully', 'success');
        }
    } catch (error) {
        statusDiv.textContent = 'Failed to change password';
        statusDiv.className = 'upload-status error';
    }
}

async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        if (data.success) {
            displayUsers(data.users, data.current_user);
        }
    } catch (error) {
        console.error('Failed to load users:', error);
    }
}

function displayUsers(users, currentUser) {
    const usersList = document.getElementById('users-list');
    
    if (!users || users.length === 0) {
        usersList.innerHTML = '<p>No users found</p>';
        return;
    }
    
    usersList.innerHTML = users.map(username => `
        <div class="user-item ${username === currentUser ? 'current-user' : ''}">
            <div class="user-info">
                <strong>${username}</strong>
                ${username === currentUser ? '<span class="user-badge">You</span>' : ''}
            </div>
            ${username !== currentUser ? `
                <button class="btn btn-danger" onclick="deleteUser('${username}')">
                    🗑️ Delete
                </button>
            ` : '<span style="color: var(--text-muted); font-size: 0.9em;">Current user</span>'}
        </div>
    `).join('');
}

async function addUser() {
    const username = document.getElementById('new-username').value.trim();
    const password = document.getElementById('new-user-password').value;
    const statusDiv = document.getElementById('add-user-status');
    
    if (!username || !password) {
        statusDiv.textContent = 'Please fill in all fields';
        statusDiv.className = 'upload-status error';
        return;
    }
    
    try {
        const response = await fetch('/api/users/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        statusDiv.textContent = data.message;
        statusDiv.className = data.success ? 'upload-status success' : 'upload-status error';
        
        if (data.success) {
            document.getElementById('new-username').value = '';
            document.getElementById('new-user-password').value = '';
            showNotification(data.message, 'success');
            loadUsers();
        }
    } catch (error) {
        statusDiv.textContent = 'Failed to add user';
        statusDiv.className = 'upload-status error';
    }
}

async function deleteUser(username) {
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/users/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        
        if (await handleApiError(response)) return;
        const data = await response.json();
        
        showNotification(data.message, data.success ? 'success' : 'error');
        
        if (data.success) {
            loadUsers();
        }
    } catch (error) {
        showNotification('Failed to delete user', 'error');
    }
}