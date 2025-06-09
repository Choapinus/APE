#!/usr/bin/env python3
"""
APE MCP Server - Entry Point

This is the main entry point for the APE (Advanced Prompt Engine) MCP server.
The server now uses the official MCP Python SDK for proper protocol compliance.
"""

import asyncio
from ape.mcp.server import run_server

if __name__ == "__main__":
    # Run the MCP server
    asyncio.run(run_server()) 