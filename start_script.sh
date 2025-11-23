#!/bin/bash

# Create necessary directories
mkdir -p /minecraft/worlds /minecraft/plugins /minecraft/logs

# Start the Flask web application
cd /app
python app.py &

# Keep container running
tail -f /dev/null