# Minecraft Server Manager

A Docker-based Minecraft server management solution with a web admin panel for easy server control, version management, and world uploads.

## Features

- 🔐 Secure login authentication with user management
- 👥 Add/remove multiple users with individual accounts
- 🔑 Change passwords from the web interface
- 🎮 Full Minecraft server management via web interface
- 📦 Easy version upgrades by uploading server JAR files
- 🗺️ World upload and management
- 🔧 Real-time server console
- ⚙️ Server configuration management
- 📊 Server status monitoring
- 🔄 Start/Stop/Restart controls
- 🎨 Modern Discord-inspired dark theme UI

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Ports 25565 (Minecraft) and 8080 (Web Panel) available

### Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/minecraft-server-manager.git
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

### Uploading Worlds
1. Navigate to the "Worlds" section
2. Upload a zipped world folder
3. Select the world to use
4. Restart the server

### Version Upgrades
1. Download the new server JAR from minecraft.net or your preferred source
2. Upload via the "Server JAR" section
3. Restart the server

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
- `SECRET_KEY`: Flask session secret key (auto-generated if not set)

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
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

Note: Environment variable only affects the initial setup. Once users are created, use the web interface to manage passwords.

## Volumes

- `./data`: Persistent storage for Minecraft server files
- `./backups`: Automatic world backups

## Security Notes

- Change the default admin password immediately
- Use a reverse proxy (nginx/traefik) with SSL for production
- Restrict web panel access using firewall rules
- Regular backups are recommended

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue on GitHub.