FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Add /app to PYTHONPATH so Python can find the 'ape' package
ENV PYTHONPATH=/app:$PYTHONPATH

# Expose the port for the MCP server
EXPOSE 8000
