#!/usr/bin/env python3
"""
APE MCP Server - HTTP Entry Point

This script runs the MCP server as a standalone HTTP (ASGI) application using uvicorn.
"""

import uvicorn
from ape.mcp.server import app
from ape.settings import settings
from ape.utils import setup_logger

if __name__ == "__main__":
    setup_logger()
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT) 