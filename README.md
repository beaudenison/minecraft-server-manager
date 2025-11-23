# Minecraft Server Manager

A Docker-based Minecraft server management solution with a web admin panel for easy server control, version management, and world uploads.

## Features

- 🎮 Full Minecraft server management via web interface
- 📦 Easy version upgrades by uploading server JAR files
- 🗺️ World upload and management
- 🔧 Real-time server console
- ⚙️ Server configuration management
- 📊 Server status monitoring
- 🔄 Start/Stop/Restart controls

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

4. Default login credentials:
   - Username: `admin`
   - Password: `changeme` (change this immediately!)

## Usage

### First Time Setup
1. Access the web panel
2. Upload a Minecraft server JAR file (e.g., `server.jar`)
3. Configure server properties
4. Accept the EULA
5. Start the server

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
- `ADMIN_PASSWORD`: Admin panel password

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