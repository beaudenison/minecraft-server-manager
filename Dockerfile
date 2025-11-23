FROM python:3.11-slim

# Install Java 21 (latest LTS) and other dependencies
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    wget \
    unzip \
    screen \
    && rm -rf /var/lib/apt/lists/*

# Create working directories
WORKDIR /app
RUN mkdir -p /minecraft /backups

# Copy web application
COPY web/ /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose ports
EXPOSE 25565 8080

# Set environment variables
ENV MC_MEMORY=2G
ENV PYTHONUNBUFFERED=1

# Start both web server and minecraft server manager
CMD ["/start.sh"]