# Multi-stage Dockerfile for APE MCP Server and Agent
FROM python:3.11-slim-bookworm as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create non-root user for security
RUN groupadd -r apeuser && useradd -r -g apeuser apeuser
RUN chown -R apeuser:apeuser /app

# Switch to non-root user
USER apeuser

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Default command (will be overridden in docker-compose)
CMD ["python", "mcp_server.py"]
