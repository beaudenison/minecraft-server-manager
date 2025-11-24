# Minecraft Server Manager

A Docker-based Minecraft server management solution with a web admin panel for easy server control, version management, and world uploads.

## Features

- 🔐 Secure login authentication with user management
- 👥 Add/remove multiple users with individual accounts
- 🔑 Change passwords from the web interface
- 🎮 Full Minecraft server management via web interface
- 📦 Easy version upgrades by uploading server JAR files
- 🗺️ World upload and management
- 💾 Automatic backup system with rotation
- 🔧 Real-time server console
- 📊 Server health monitoring (CPU, memory, uptime)
- ⚙️ Server configuration management
- 🔄 Start/Stop/Restart controls
- 🛡️ Rate limiting and security features
- 📝 Comprehensive logging
- 🎨 Modern Discord-inspired dark theme UI

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Ports 25565 (Minecraft) and 8080 (Web Panel) available

### Installation

1. Clone this repository:
```bash
git clone https://github.com/beaudenison/minecraft-server-manager.git
cd minecraft-server-manager
```

2. Start the container:
```bash
docker-compose up -d
```

3. Access the web panel at `http://localhost:8080`

4. **Login credentials:**
   - Username: `admin`
   - Password: `changeme`
   
   ⚠️ **Important:** Change the admin password by setting the `ADMIN_PASSWORD` environment variable in docker-compose.yml

## Usage

### First Time Setup
1. Access the web panel at `http://localhost:8080`
2. Login with default credentials (admin / changeme)
3. **Immediately change your password** in the Users tab
4. Upload a Minecraft server JAR file
5. Configure server properties if needed
6. Start the server

### Managing Users
1. Go to the **Users** tab
2. **Change Your Password**: Update your current password
3. **Add New User**: Create additional user accounts
4. **Delete User**: Remove users (cannot delete yourself or the last user)

All user data is stored in `/minecraft/users.json` and persists across container restarts.

### Server Monitoring
The console tab displays real-time server health metrics:
- **CPU Usage**: Current CPU utilization percentage
- **Memory Usage**: RAM consumption in MB
- **Uptime**: How long the server has been running

### Backup Management
1. Navigate to the **Backups** tab
2. Click "Create Backup Now" to create a backup of the active world
3. Backups are automatically rotated (last 10 are kept)
4. View backup size and creation time

### Uploading Worlds
1. Navigate to the "Worlds" section
2. Upload a zipped world folder
3. The world is automatically set as active and will be used on next server start
4. If the server is running, it will be restarted automatically to use the new world

**Note**: The system automatically handles different ZIP structures:
- If your ZIP contains a single root folder with the world data, it will extract the contents correctly
- If your ZIP has world files at the root level (level.dat, region/, etc.), it will work as-is
- The system validates that level.dat exists and will show an error if the world format is invalid

### Version Upgrades
1. Download the new server JAR from minecraft.net or your preferred source
2. Upload via the "Server JAR" section
3. Restart the server

## Security Features

- **Rate Limiting**: Prevents API abuse with configurable limits
- **Session Security**: HTTP-only cookies with secure flags
- **Input Validation**: All user inputs are sanitized
- **File Upload Security**: Size limits and content validation
- **Automatic Backups**: Protect your worlds from data loss
- **Comprehensive Logging**: Track all server activities

## Directory Structure

```
minecraft-server-manager/
├── docker-compose.yml
├── Dockerfile
├── web/
│   ├── app.py              # Flask web application
│   ├── requirements.txt    # Python dependencies
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── main.js
│   └── templates/
│       └── index.html
└── data/                   # Minecraft server data (auto-created)
    ├── server.jar
    ├── worlds/
    ├── plugins/
    └── server.properties
```

## Environment Variables

- `MC_PORT`: Minecraft server port (default: 25565)
- `WEB_PORT`: Web panel port (default: 8080)
- `MC_MEMORY`: Server memory allocation (default: 2G)
- `ADMIN_PASSWORD`: Admin panel password (default: changeme) - **Change this!**
- `SECRET_KEY`: Flask session secret key (strongly recommended for production) - if not set, uses a development default

### Changing the Admin Password

**Method 1: Through Web Interface (Recommended)**
1. Login to the web panel
2. Go to the **Users** tab
3. Enter your current password and new password
4. Click "Change Password"

**Method 2: Through Environment Variable**
Edit `docker-compose.yml` and change the `ADMIN_PASSWORD` variable:

```yaml
environment:
  - MC_MEMORY=2G
  - ADMIN_PASSWORD=your_secure_password_here
  - SECRET_KEY=your_random_secret_key_here  # Generate with: python3 -c "import os; print(os.urandom(32).hex())"
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

Note: Environment variable only affects the initial setup. Once users are created, use the web interface to manage passwords.

## Volumes

- `./data`: Persistent storage for Minecraft server files
- `./backups`: Automatic world backups (last 10 retained)

## Logs

Application logs are stored in `/minecraft/logs/manager.log` and include:
- User authentication events
- Server start/stop operations
- Backup creation
- File uploads
- Error messages

## Security Notes

- Change the default admin password immediately
- Use a reverse proxy (nginx/traefik) with SSL for production
- Restrict web panel access using firewall rules
- Regular backups are created automatically
- Rate limiting is enabled to prevent API abuse
- All file uploads are validated for security

## Performance Improvements

This version includes several performance enhancements:
- Efficient console output buffering
- Optimized file operations with atomic writes
- Smart health monitoring
- Reduced polling overhead
- Proper process cleanup on shutdown

## Troubleshooting

### Server won't start
- Check logs in `/minecraft/logs/manager.log`
- Ensure server.jar is uploaded
- Verify Java version compatibility (requires Java 21)
- Check memory allocation (default 2G)

### High memory usage
- Adjust MC_MEMORY environment variable in docker-compose.yml
- Check for memory leaks in console output
- Monitor health metrics in the web panel

### Backup failures
- Ensure adequate disk space in ./backups directory
- Check file permissions
- Review logs for specific error messages

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on GitHub.