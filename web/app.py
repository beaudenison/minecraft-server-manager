from flask import Flask, render_template, request, jsonify, send_file
import os
import subprocess
import signal
import zipfile
import shutil
import time
import threading
from werkzeug.utils import secure_filename
from collections import deque

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

MC_DIR = '/minecraft'
BACKUP_DIR = '/backups'
ALLOWED_EXTENSIONS = {'jar', 'zip'}

# Store server process and console output
mc_process = None
console_output = deque(maxlen=1000)
console_lock = threading.Lock()

def allowed_file(filename, extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def get_server_status():
    global mc_process
    if mc_process and mc_process.poll() is None:
        return 'running'
    return 'stopped'

def read_console_output(process):
    """Read console output from minecraft server"""
    global console_output
    try:
        for line in iter(process.stdout.readline, b''):
            decoded = line.decode('utf-8', errors='ignore').strip()
            with console_lock:
                console_output.append(decoded)
    except:
        pass

def start_minecraft_server():
    global mc_process, console_output
    
    if mc_process and mc_process.poll() is None:
        return False, "Server is already running"
    
    server_jar = os.path.join(MC_DIR, 'server.jar')
    if not os.path.exists(server_jar):
        return False, "No server.jar found. Please upload a server JAR file first."
    
    eula_path = os.path.join(MC_DIR, 'eula.txt')
    if not os.path.exists(eula_path):
        with open(eula_path, 'w') as f:
            f.write('eula=true\n')
    
    memory = os.environ.get('MC_MEMORY', '2G')
    
    try:
        with console_lock:
            console_output.clear()
            console_output.append("Starting Minecraft server...")
        
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
        
        return True, "Server starting..."
    except Exception as e:
        return False, f"Failed to start server: {str(e)}"

def stop_minecraft_server():
    global mc_process
    
    if not mc_process or mc_process.poll() is not None:
        return False, "Server is not running"
    
    try:
        # Send stop command
        mc_process.stdin.write(b'stop\n')
        mc_process.stdin.flush()
        
        # Wait for graceful shutdown
        try:
            mc_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            mc_process.kill()
        
        with console_lock:
            console_output.append("Server stopped")
        
        return True, "Server stopped"
    except Exception as e:
        return False, f"Failed to stop server: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    status = get_server_status()
    
    # Check if server.jar exists
    has_jar = os.path.exists(os.path.join(MC_DIR, 'server.jar'))
    
    # Get world folders
    worlds = []
    worlds_dir = os.path.join(MC_DIR, 'worlds')
    if os.path.exists(worlds_dir):
        worlds = [d for d in os.listdir(worlds_dir) if os.path.isdir(os.path.join(worlds_dir, d))]
    
    # Check active world
    properties_path = os.path.join(MC_DIR, 'server.properties')
    active_world = 'world'
    if os.path.exists(properties_path):
        with open(properties_path, 'r') as f:
            for line in f:
                if line.startswith('level-name='):
                    active_world = line.split('=')[1].strip()
                    break
    
    return jsonify({
        'status': status,
        'has_jar': has_jar,
        'worlds': worlds,
        'active_world': active_world
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    success, message = start_minecraft_server()
    return jsonify({'success': success, 'message': message})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    success, message = stop_minecraft_server()
    return jsonify({'success': success, 'message': message})

@app.route('/api/restart', methods=['POST'])
def api_restart():
    stop_minecraft_server()
    time.sleep(2)
    success, message = start_minecraft_server()
    return jsonify({'success': success, 'message': message})

@app.route('/api/console')
def api_console():
    with console_lock:
        output = list(console_output)
    return jsonify({'output': output})

@app.route('/api/command', methods=['POST'])
def api_command():
    global mc_process
    
    if not mc_process or mc_process.poll() is not None:
        return jsonify({'success': False, 'message': 'Server is not running'})
    
    command = request.json.get('command', '')
    if not command:
        return jsonify({'success': False, 'message': 'No command provided'})
    
    try:
        mc_process.stdin.write(f"{command}\n".encode())
        mc_process.stdin.flush()
        return jsonify({'success': True, 'message': 'Command sent'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send command: {str(e)}'})

@app.route('/api/upload-jar', methods=['POST'])
def api_upload_jar():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not allowed_file(file.filename, {'jar'}):
        return jsonify({'success': False, 'message': 'Only .jar files are allowed'})
    
    # Stop server if running
    if get_server_status() == 'running':
        stop_minecraft_server()
        time.sleep(2)
    
    # Save the JAR file
    jar_path = os.path.join(MC_DIR, 'server.jar')
    try:
        file.save(jar_path)
        return jsonify({'success': True, 'message': 'Server JAR uploaded successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to upload JAR: {str(e)}'})

@app.route('/api/upload-world', methods=['POST'])
def api_upload_world():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not allowed_file(file.filename, {'zip'}):
        return jsonify({'success': False, 'message': 'Only .zip files are allowed'})
    
    # Stop server if running
    was_running = get_server_status() == 'running'
    if was_running:
        stop_minecraft_server()
        time.sleep(2)
    
    try:
        # Save uploaded zip
        zip_path = os.path.join(MC_DIR, 'temp_world.zip')
        file.save(zip_path)
        
        # Extract world
        world_name = secure_filename(file.filename.rsplit('.', 1)[0])
        world_path = os.path.join(MC_DIR, 'worlds', world_name)
        
        # Create worlds directory if it doesn't exist
        os.makedirs(os.path.join(MC_DIR, 'worlds'), exist_ok=True)
        
        # Remove existing world with same name
        if os.path.exists(world_path):
            shutil.rmtree(world_path)
        
        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(world_path)
        
        # Clean up
        os.remove(zip_path)
        
        message = f'World "{world_name}" uploaded successfully'
        if was_running:
            start_minecraft_server()
            message += ' and server restarted'
        
        return jsonify({'success': True, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to upload world: {str(e)}'})

@app.route('/api/set-world', methods=['POST'])
def api_set_world():
    world_name = request.json.get('world')
    if not world_name:
        return jsonify({'success': False, 'message': 'No world name provided'})
    
    properties_path = os.path.join(MC_DIR, 'server.properties')
    
    try:
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
        
        # Write back
        with open(properties_path, 'w') as f:
            f.writelines(lines)
        
        return jsonify({'success': True, 'message': f'Active world set to "{world_name}". Restart server to apply.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to set world: {str(e)}'})

@app.route('/api/properties', methods=['GET', 'POST'])
def api_properties():
    properties_path = os.path.join(MC_DIR, 'server.properties')
    
    if request.method == 'GET':
        if os.path.exists(properties_path):
            with open(properties_path, 'r') as f:
                content = f.read()
            return jsonify({'success': True, 'content': content})
        return jsonify({'success': False, 'message': 'No server.properties found'})
    
    else:  # POST
        content = request.json.get('content', '')
        try:
            with open(properties_path, 'w') as f:
                f.write(content)
            return jsonify({'success': True, 'message': 'Properties saved. Restart server to apply changes.'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Failed to save properties: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)