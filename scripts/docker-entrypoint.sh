#!/bin/sh
set -e

# This script runs as root to perform initial setup, then drops privileges.

# 1. Fix ownership of directories the non-root user needs to write to.
chown -R apeuser:apeuser /app/data
mkdir -p /app/logs && chown -R apeuser:apeuser /app/logs
mkdir -p /app/database && chown -R apeuser:apeuser /app/database
chown -R apeuser:apeuser /home/apeuser

# 2. Ensure the shared JWT secret exists.
SECRET_PATH="/app/data/jwt.secret"
if [ ! -f "$SECRET_PATH" ]; then
    echo "Generating new shared JWT secret..."
    # Generate the key and ensure it's owned by apeuser.
    openssl rand -hex 32 > "$SECRET_PATH"
    chmod 400 "$SECRET_PATH"
    chown apeuser:apeuser "$SECRET_PATH"
fi

# 3. Read the key value.
KEY_VALUE=$(cat "$SECRET_PATH")

# 4. Drop privileges and execute the final command.
#    We pass the secret key and PYTHONPATH via `env`.
#    "$@" is the CMD from the Dockerfile or the `command` from docker-compose.
exec gosu apeuser:apeuser env MCP_JWT_KEY="$KEY_VALUE" PYTHONPATH="/app:$PYTHONPATH" "$@"
