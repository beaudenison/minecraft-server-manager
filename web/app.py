from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import os
import subprocess
import signal
import zipfile
import shutil
import time
import threading
import json
import logging
import atexit
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from collections import deque
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import psutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
# Use a persistent secret key - in production this should be set via environment variable
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-use-env-var'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/minecraft/logs/manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

MC_DIR = '/minecraft'
BACKUP_DIR = '/backups'
USERS_FILE = '/minecraft/users.json'
LOG_DIR = '/minecraft/logs'
ALLOWED_EXTENSIONS = {'jar', 'zip'}
MAX_BACKUP_COUNT = 10  # Keep last 10 backups

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Load or create users
def load_users():
    """Load users from file with error handling."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                users_data = json.load(f)
                logger.info(f"Loaded {len(users_data)} users from file")
                return users_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse users file: {e}")
        except Exception as e:
            logger.error(f"Error loading users: {e}")
    
    # Default user if file doesn't exist or is corrupted
    default_users = {
        'admin': generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'changeme'))
    }
    save_users(default_users)
    logger.info("Created default admin user")
    return default_users

def save_users(users_dict):
    """Save users to file with atomic write."""
    try:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        # Write to temporary file first
        temp_file = USERS_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(users_dict, f, indent=2)
        # Atomic rename
        os.replace(temp_file, USERS_FILE)
        logger.info(f"Saved {len(users_dict)} users to file")
    except Exception as e:
        logger.error(f"Failed to save users: {e}")
        raise

users = load_users()

# Store server process and console output
mc_process = None
console_output = deque(maxlen=1000)
console_lock = threading.Lock()

def cleanup_minecraft_process():
    """Ensure Minecraft server is properly stopped on exit."""
    global mc_process
    if mc_process and mc_process.poll() is None:
        logger.info("Cleaning up Minecraft server process...")
        try:
            mc_process.stdin.write(b'stop\n')
            mc_process.stdin.flush()
            mc_process.wait(timeout=30)
        except:
            mc_process.kill()
        logger.info("Minecraft server stopped")

# Register cleanup handler
atexit.register(cleanup_minecraft_process)

def create_backup(backup_name=None):
    """Create a backup of the current world."""
    try:
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Get active world name
        properties_path = os.path.join(MC_DIR, 'server.properties')
        world_name = 'world'
        if os.path.exists(properties_path):
            with open(properties_path, 'r') as f:
                for line in f:
                    if line.startswith('level-name='):
                        world_name = line.split('=')[1].strip()
                        break
        
        world_path = os.path.join(MC_DIR, world_name)
        if not os.path.exists(world_path):
            logger.warning(f"World path {world_path} does not exist")
            return False, "World not found"
        
        backup_path = os.path.join(BACKUP_DIR, f"{backup_name}.zip")
        
        # Create zip backup
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(world_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, MC_DIR)
                    zipf.write(file_path, arcname)
        
        logger.info(f"Created backup: {backup_name}")
        
        # Clean up old backups
        cleanup_old_backups()
        
        return True, f"Backup created: {backup_name}"
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False, f"Backup failed: {str(e)}"

def cleanup_old_backups():
    """Remove old backups, keeping only the most recent ones."""
    try:
        backups = []
        for file in os.listdir(BACKUP_DIR):
            if file.endswith('.zip'):
                file_path = os.path.join(BACKUP_DIR, file)
                backups.append((file_path, os.path.getmtime(file_path)))
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old backups
        for backup_path, _ in backups[MAX_BACKUP_COUNT:]:
            os.remove(backup_path)
            logger.info(f"Removed old backup: {os.path.basename(backup_path)}")
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")

def allowed_file(filename, extensions):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def validate_file_upload(file, allowed_extensions, max_size=None):
    """Validate uploaded file."""
    if not file or file.filename == '':
        return False, 'No file selected'
    
    if not allowed_file(file.filename, allowed_extensions):
        return False, f'Only {", ".join(allowed_extensions)} files are allowed'
    
    if max_size:
        # Check file size by seeking to end
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > max_size:
            return False, f'File too large (max {max_size // (1024*1024)}MB)'
    
    return True, 'Valid'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_server_status():
    """Get detailed server status."""
    global mc_process
    if mc_process and mc_process.poll() is None:
        return 'running'
    return 'stopped'

def get_server_health():
    """Get server health metrics."""
    global mc_process
    health = {
        'status': get_server_status(),
        'pid': None,
        'cpu_percent': 0,
        'memory_mb': 0,
        'uptime_seconds': 0
    }
    
    if mc_process and mc_process.poll() is None:
        try:
            process = psutil.Process(mc_process.pid)
            health['pid'] = mc_process.pid
            # Use non-blocking CPU measurement to avoid delays
            health['cpu_percent'] = process.cpu_percent(interval=None)
            health['memory_mb'] = process.memory_info().rss / (1024 * 1024)
            health['uptime_seconds'] = int(time.time() - process.create_time())
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning(f"Failed to get process info: {e}")
    
    return health

def read_console_output(process):
    """Read console output from minecraft server with improved error handling."""
    global console_output
    try:
        for line in iter(process.stdout.readline, b''):
            if not line:
                break
            decoded = line.decode('utf-8', errors='ignore').strip()
            if decoded:  # Only add non-empty lines
                with console_lock:
                    console_output.append(decoded)
                logger.debug(f"MC: {decoded}")
    except Exception as e:
        logger.error(f"Error reading console output: {e}")
        with console_lock:
            console_output.append(f"[ERROR] Console reader stopped: {str(e)}")

def start_minecraft_server():
    """Start the Minecraft server with improved error handling."""
    global mc_process, console_output
    
    if mc_process and mc_process.poll() is None:
        logger.warning("Attempted to start server that is already running")
        return False, "Server is already running"
    
    server_jar = os.path.join(MC_DIR, 'server.jar')
    if not os.path.exists(server_jar):
        logger.error("No server.jar found")
        return False, "No server.jar found. Please upload a server JAR file first."
    
    # Accept EULA
    eula_path = os.path.join(MC_DIR, 'eula.txt')
    if not os.path.exists(eula_path):
        with open(eula_path, 'w') as f:
            f.write('eula=true\n')
        logger.info("Created eula.txt")
    
    memory = os.environ.get('MC_MEMORY', '2G')
    
    try:
        with console_lock:
            console_output.clear()
            console_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Minecraft server with {memory} memory...")
        
        mc_process = subprocess.Popen(
            ['java', f'-Xmx{memory}', f'-Xms{memory}', '-jar', 'server.jar', 'nogui'],
            cwd=MC_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            bufsize=1
        )
        
        # Start thread to read console output
        threading.Thread(target=read_console_output, args=(mc_process,), daemon=True).start()
        
        logger.info(f"Started Minecraft server with PID {mc_process.pid}")
        return True, "Server starting..."
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return False, f"Failed to start server: {str(e)}"

def stop_minecraft_server():
    """Stop the Minecraft server gracefully."""
    global mc_process
    
    if not mc_process or mc_process.poll() is not None:
        logger.warning("Attempted to stop server that is not running")
        return False, "Server is not running"
    
    try:
        logger.info(f"Stopping Minecraft server (PID {mc_process.pid})...")
        
        # Send stop command
        mc_process.stdin.write(b'stop\n')
        mc_process.stdin.flush()
        
        with console_lock:
            console_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Stopping server...")
        
        # Wait for graceful shutdown
        try:
            mc_process.wait(timeout=30)
            logger.info("Server stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("Server didn't stop gracefully, forcing shutdown")
            mc_process.kill()
            mc_process.wait()
        
        # Reset process variable to None after stopping
        mc_process = None
        
        with console_lock:
            console_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Server stopped")
        
        return True, "Server stopped"
    except Exception as e:
        logger.error(f"Failed to stop server: {e}")
        # Reset process variable even on error
        mc_process = None
        return False, f"Failed to stop server: {str(e)}"

@app.route('/')
def index():
    if 'logged_in' not in session:
        return render_template('login.html')
    return render_template('index.html')

@app.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """Handle user login with rate limiting."""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            logger.warning(f"Login attempt with missing credentials from {request.remote_addr}")
            return jsonify({'success': False, 'message': 'Username and password required'}), 400
        
        if username in users and check_password_hash(users[username], password):
            session['logged_in'] = True
            session['username'] = username
            session.permanent = True
            logger.info(f"User {username} logged in from {request.remote_addr}")
            return jsonify({'success': True, 'message': 'Login successful'})
        
        logger.warning(f"Failed login attempt for user {username} from {request.remote_addr}")
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/logout', methods=['POST'])
def logout():
    """Handle user logout."""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/change-password', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def api_change_password():
    """Change user password with validation."""
    global users
    try:
        data = request.json
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': 'Please provide both current and new password'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400
        
        username = session.get('username')
        
        # Verify current password
        if not check_password_hash(users[username], current_password):
            logger.warning(f"User {username} failed to change password (incorrect current password)")
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 401
        
        # Update password
        users[username] = generate_password_hash(new_password)
        save_users(users)
        
        logger.info(f"User {username} changed their password")
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({'success': False, 'message': 'Failed to change password'}), 500

@app.route('/api/users', methods=['GET'])
@login_required
def api_get_users():
    # Return list of usernames (not passwords)
    return jsonify({
        'success': True,
        'users': list(users.keys()),
        'current_user': session.get('username')
    })

@app.route('/api/users/add', methods=['POST'])
@login_required
def api_add_user():
    global users
    data = request.json
    new_username = data.get('username')
    new_password = data.get('password')
    
    if not new_username or not new_password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    if new_username in users:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    if len(new_username) < 3:
        return jsonify({'success': False, 'message': 'Username must be at least 3 characters'})
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})
    
    users[new_username] = generate_password_hash(new_password)
    save_users(users)
    
    return jsonify({'success': True, 'message': f'User {new_username} created successfully'})

@app.route('/api/users/delete', methods=['POST'])
@login_required
def api_delete_user():
    global users
    data = request.json
    username_to_delete = data.get('username')
    
    if not username_to_delete:
        return jsonify({'success': False, 'message': 'Username required'})
    
    if username_to_delete == session.get('username'):
        return jsonify({'success': False, 'message': 'Cannot delete your own account'})
    
    if username_to_delete not in users:
        return jsonify({'success': False, 'message': 'User not found'})
    
    if len(users) == 1:
        return jsonify({'success': False, 'message': 'Cannot delete the last user'})
    
    del users[username_to_delete]
    save_users(users)
    
    return jsonify({'success': True, 'message': f'User {username_to_delete} deleted successfully'})

@app.route('/api/status')
@login_required
def api_status():
    """Get comprehensive server status."""
    try:
        status = get_server_status()
        health = get_server_health()
        
        # Check if server.jar exists
        has_jar = os.path.exists(os.path.join(MC_DIR, 'server.jar'))
        
        # Get world folders - look for directories with level.dat (Minecraft worlds)
        worlds = []
        if os.path.exists(MC_DIR):
            for item in os.listdir(MC_DIR):
                item_path = os.path.join(MC_DIR, item)
                # Check if it's a directory and contains level.dat (Minecraft world indicator)
                if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'level.dat')):
                    worlds.append(item)
        
        # Check active world
        properties_path = os.path.join(MC_DIR, 'server.properties')
        active_world = 'world'
        if os.path.exists(properties_path):
            with open(properties_path, 'r') as f:
                for line in f:
                    if line.startswith('level-name='):
                        active_world = line.split('=')[1].strip()
                        break
        
        # Get backup count
        backup_count = 0
        if os.path.exists(BACKUP_DIR):
            backup_count = len([f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')])
        
        return jsonify({
            'status': status,
            'has_jar': has_jar,
            'worlds': worlds,
            'active_world': active_world,
            'health': health,
            'backup_count': backup_count
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': 'Failed to get status'}), 500

@app.route('/api/start', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def api_start():
    """Start the Minecraft server."""
    try:
        success, message = start_minecraft_server()
        logger.info(f"Server start requested by {session.get('username')}: {message}")
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return jsonify({'success': False, 'message': 'Failed to start server'}), 500

@app.route('/api/stop', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def api_stop():
    """Stop the Minecraft server."""
    try:
        success, message = stop_minecraft_server()
        logger.info(f"Server stop requested by {session.get('username')}: {message}")
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Error stopping server: {e}")
        return jsonify({'success': False, 'message': 'Failed to stop server'}), 500

@app.route('/api/restart', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def api_restart():
    """Restart the Minecraft server."""
    try:
        logger.info(f"Server restart requested by {session.get('username')}")
        stop_minecraft_server()
        time.sleep(2)
        success, message = start_minecraft_server()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Error restarting server: {e}")
        return jsonify({'success': False, 'message': 'Failed to restart server'}), 500

@app.route('/api/backup', methods=['POST'])
@login_required
@limiter.limit("5 per hour")
def api_backup():
    """Create a backup of the current world."""
    try:
        data = request.json or {}
        backup_name = data.get('name')
        
        # Validate backup name if provided
        if backup_name:
            backup_name = secure_filename(backup_name)
            if not backup_name:
                return jsonify({'success': False, 'message': 'Invalid backup name'}), 400
        
        logger.info(f"Backup requested by {session.get('username')}")
        success, message = create_backup(backup_name)
        
        if success:
            logger.info(f"Backup created successfully: {message}")
        else:
            logger.error(f"Backup failed: {message}")
        
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return jsonify({'success': False, 'message': f'Backup failed: {str(e)}'}), 500

@app.route('/api/backups', methods=['GET'])
@login_required
def api_list_backups():
    """List all available backups."""
    try:
        backups = []
        if os.path.exists(BACKUP_DIR):
            for file in os.listdir(BACKUP_DIR):
                if file.endswith('.zip'):
                    file_path = os.path.join(BACKUP_DIR, file)
                    stat = os.stat(file_path)
                    backups.append({
                        'name': file,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify({'success': True, 'backups': backups})
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return jsonify({'success': False, 'message': 'Failed to list backups'}), 500

@app.route('/api/console')
@login_required
def api_console():
    """Get console output."""
    try:
        with console_lock:
            output = list(console_output)
        return jsonify({'output': output, 'line_count': len(output)})
    except Exception as e:
        logger.error(f"Error getting console output: {e}")
        return jsonify({'output': [], 'error': 'Failed to get console output'}), 500

@app.route('/api/command', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def api_command():
    """Send a command to the Minecraft server."""
    global mc_process
    
    try:
        if not mc_process or mc_process.poll() is not None:
            return jsonify({'success': False, 'message': 'Server is not running'}), 400
        
        command = request.json.get('command', '').strip()
        if not command:
            return jsonify({'success': False, 'message': 'No command provided'}), 400
        
        # Sanitize command - prevent injection
        if '\n' in command or '\r' in command:
            return jsonify({'success': False, 'message': 'Invalid command format'}), 400
        
        mc_process.stdin.write(f"{command}\n".encode())
        mc_process.stdin.flush()
        
        logger.info(f"Command sent by {session.get('username')}: {command}")
        return jsonify({'success': True, 'message': 'Command sent'})
    except BrokenPipeError:
        logger.error("Broken pipe when sending command")
        return jsonify({'success': False, 'message': 'Server connection lost'}), 500
    except Exception as e:
        logger.error(f"Failed to send command: {e}")
        return jsonify({'success': False, 'message': f'Failed to send command: {str(e)}'}), 500

@app.route('/api/upload-jar', methods=['POST'])
@login_required
@limiter.limit("5 per hour")
def api_upload_jar():
    """Upload a new server JAR file."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        # Validate file
        valid, message = validate_file_upload(file, {'jar'}, max_size=200*1024*1024)  # 200MB max
        if not valid:
            logger.warning(f"Invalid JAR upload attempt by {session.get('username')}: {message}")
            return jsonify({'success': False, 'message': message}), 400
        
        # Stop server if running
        was_running = get_server_status() == 'running'
        if was_running:
            stop_minecraft_server()
            time.sleep(2)
        
        # Backup old JAR if it exists
        jar_path = os.path.join(MC_DIR, 'server.jar')
        if os.path.exists(jar_path):
            backup_path = os.path.join(MC_DIR, f'server.jar.backup.{int(time.time())}')
            shutil.copy2(jar_path, backup_path)
            logger.info(f"Backed up old server.jar to {backup_path}")
        
        # Save the new JAR file
        file.save(jar_path)
        
        logger.info(f"Server JAR uploaded by {session.get('username')}: {file.filename}")
        
        message = 'Server JAR uploaded successfully'
        if was_running:
            success, start_msg = start_minecraft_server()
            message += f'. {start_msg}'
        
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"Failed to upload JAR: {e}")
        return jsonify({'success': False, 'message': f'Failed to upload JAR: {str(e)}'}), 500

@app.route('/api/upload-world', methods=['POST'])
@login_required
@limiter.limit("3 per hour")
def api_upload_world():
    """Upload a world file."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        # Validate file
        valid, message = validate_file_upload(file, {'zip'})
        if not valid:
            logger.warning(f"Invalid world upload attempt by {session.get('username')}: {message}")
            return jsonify({'success': False, 'message': message}), 400
        
        # Stop server if running
        was_running = get_server_status() == 'running'
        if was_running:
            stop_minecraft_server()
            time.sleep(2)
        
        # Save uploaded zip
        zip_path = os.path.join(MC_DIR, 'temp_world.zip')
        file.save(zip_path)
        
        # Extract world
        world_name = secure_filename(file.filename.rsplit('.', 1)[0])
        if not world_name:
            world_name = f"world_{int(time.time())}"
        
        # World goes directly in MC_DIR, not in a subdirectory
        world_path = os.path.join(MC_DIR, world_name)
        
        # Remove existing world with same name
        if os.path.exists(world_path):
            # Backup existing world before removing
            backup_path = world_path + f'.backup.{int(time.time())}'
            shutil.move(world_path, backup_path)
            logger.info(f"Backed up existing world to: {backup_path}")
        
        # Extract zip to temporary location first
        temp_extract_path = os.path.join(MC_DIR, f'temp_extract_{int(time.time())}')
        os.makedirs(temp_extract_path, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Security check: ensure no path traversal
                for member in zip_ref.namelist():
                    if member.startswith('..') or member.startswith('/'):
                        os.remove(zip_path)
                        shutil.rmtree(temp_extract_path)
                        return jsonify({'success': False, 'message': 'Invalid zip file structure'}), 400
                zip_ref.extractall(temp_extract_path)
            
            # Check if extracted content has a single root directory
            extracted_items = os.listdir(temp_extract_path)
            
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_path, extracted_items[0])):
                # Single root directory - move its contents to world_path
                root_dir = os.path.join(temp_extract_path, extracted_items[0])
                shutil.move(root_dir, world_path)
                logger.info(f"Extracted world from single root directory: {extracted_items[0]}")
            else:
                # Multiple items or files at root - move entire temp directory
                shutil.move(temp_extract_path, world_path)
                logger.info(f"Extracted world with multiple root items")
            
            # Clean up
            if os.path.exists(temp_extract_path):
                shutil.rmtree(temp_extract_path)
            os.remove(zip_path)
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_extract_path):
                shutil.rmtree(temp_extract_path)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise
        
        logger.info(f"World '{world_name}' uploaded by {session.get('username')}")
        
        # Verify the world has necessary files
        if not os.path.exists(os.path.join(world_path, 'level.dat')):
            logger.error(f"Uploaded world '{world_name}' missing level.dat file")
            if os.path.exists(world_path):
                shutil.rmtree(world_path)
            return jsonify({'success': False, 'message': 'Invalid world: missing level.dat file. Make sure your zip contains the world data at the root level.'}), 400
        
        # Automatically set this as the active world
        properties_path = os.path.join(MC_DIR, 'server.properties')
        if os.path.exists(properties_path):
            lines = []
            found = False
            with open(properties_path, 'r') as f:
                for line in f:
                    if line.startswith('level-name='):
                        lines.append(f'level-name={world_name}\n')
                        found = True
                    else:
                        lines.append(line)
            
            if not found:
                lines.append(f'level-name={world_name}\n')
            
            # Write back atomically
            temp_path = properties_path + '.tmp'
            with open(temp_path, 'w') as f:
                f.writelines(lines)
            os.replace(temp_path, properties_path)
            logger.info(f"Set active world to '{world_name}'")
        
        message = f'World "{world_name}" uploaded successfully and set as active world'
        if was_running:
            start_minecraft_server()
            message += '. Server restarted'
        else:
            message += '. Start the server to use this world'
        
        return jsonify({'success': True, 'message': message})
    except zipfile.BadZipFile:
        logger.error(f"Bad zip file uploaded by {session.get('username')}")
        return jsonify({'success': False, 'message': 'Invalid or corrupted zip file'}), 400
    except Exception as e:
        logger.error(f"Failed to upload world: {e}")
        return jsonify({'success': False, 'message': f'Failed to upload world: {str(e)}'}), 500

@app.route('/api/set-world', methods=['POST'])
@login_required
def api_set_world():
    """Set the active world."""
    try:
        world_name = request.json.get('world', '').strip()
        if not world_name:
            return jsonify({'success': False, 'message': 'No world name provided'}), 400
        
        # Sanitize world name
        world_name = secure_filename(world_name)
        if not world_name:
            return jsonify({'success': False, 'message': 'Invalid world name'}), 400
        
        properties_path = os.path.join(MC_DIR, 'server.properties')
        
        # Read existing properties
        lines = []
        found = False
        if os.path.exists(properties_path):
            with open(properties_path, 'r') as f:
                for line in f:
                    if line.startswith('level-name='):
                        lines.append(f'level-name={world_name}\n')
                        found = True
                    else:
                        lines.append(line)
        
        # Add if not found
        if not found:
            lines.append(f'level-name={world_name}\n')
        
        # Write back atomically
        temp_path = properties_path + '.tmp'
        with open(temp_path, 'w') as f:
            f.writelines(lines)
        os.replace(temp_path, properties_path)
        
        logger.info(f"Active world set to '{world_name}' by {session.get('username')}")
        return jsonify({'success': True, 'message': f'Active world set to "{world_name}". Restart server to apply.'})
    except Exception as e:
        logger.error(f"Failed to set world: {e}")
        return jsonify({'success': False, 'message': f'Failed to set world: {str(e)}'}), 500

@app.route('/api/properties', methods=['GET', 'POST'])
@login_required
def api_properties():
    """Get or update server properties."""
    properties_path = os.path.join(MC_DIR, 'server.properties')
    
    if request.method == 'GET':
        try:
            if os.path.exists(properties_path):
                with open(properties_path, 'r') as f:
                    content = f.read()
                return jsonify({'success': True, 'content': content})
            return jsonify({'success': False, 'message': 'No server.properties found'})
        except Exception as e:
            logger.error(f"Failed to read properties: {e}")
            return jsonify({'success': False, 'message': 'Failed to read properties'}), 500
    
    else:  # POST
        try:
            content = request.json.get('content', '')
            
            # Basic validation - ensure it's text
            if not isinstance(content, str):
                return jsonify({'success': False, 'message': 'Invalid content format'}), 400
            
            # Backup current properties
            if os.path.exists(properties_path):
                backup_path = properties_path + f'.backup.{int(time.time())}'
                shutil.copy2(properties_path, backup_path)
            
            # Write new properties atomically
            temp_path = properties_path + '.tmp'
            with open(temp_path, 'w') as f:
                f.write(content)
            os.replace(temp_path, properties_path)
            
            logger.info(f"Server properties updated by {session.get('username')}")
            return jsonify({'success': True, 'message': 'Properties saved. Restart server to apply changes.'})
        except Exception as e:
            logger.error(f"Failed to save properties: {e}")
            return jsonify({'success': False, 'message': f'Failed to save properties: {str(e)}'}), 500

@app.route('/api/health')
@login_required
def api_health():
    """Get detailed health information."""
    try:
        health = get_server_health()
        return jsonify({
            'success': True,
            'health': health,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to get health: {e}")
        return jsonify({'success': False, 'message': 'Failed to get health info'}), 500

# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error."""
    logger.warning(f"File upload too large from {request.remote_addr}")
    return jsonify({'success': False, 'message': 'File too large (max 500MB)'}), 413

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded."""
    logger.warning(f"Rate limit exceeded for {request.remote_addr}: {e.description}")
    return jsonify({'success': False, 'message': 'Rate limit exceeded. Please try again later.'}), 429

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server error."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    logger.info("Starting Minecraft Server Manager...")
    logger.info(f"MC_DIR: {MC_DIR}")
    logger.info(f"BACKUP_DIR: {BACKUP_DIR}")
    logger.info(f"LOG_DIR: {LOG_DIR}")
    app.run(host='0.0.0.0', port=8080, debug=False)