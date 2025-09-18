# Multi-stage Dockerfile for APE MCP Server and Agent
FROM python:3.11-slim-bookworm as base

WORKDIR /app

# Install system dependencies including gosu for privilege-dropping
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    gdb \
    strace \
    procps \
    util-linux \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Add and configure the entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create non-root user and its home directory
RUN groupadd -r apeuser && useradd -r -g apeuser -d /home/apeuser -m apeuser

# Set the entrypoint, which will run as root
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command (will be passed to the entrypoint)
CMD ["python", "mcp_server.py"]