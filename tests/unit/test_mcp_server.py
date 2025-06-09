#!/usr/bin/env python3
"""
Simple test script for the APE MCP Server
"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """Test the MCP server functionality."""
    
    try:
        print("🔄 Connecting to MCP server...")
        
        async with stdio_client("python", ["mcp_server.py"]) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                print("🔄 Initializing session...")
                await session.initialize()
                print("✅ Session initialized successfully!")
                
                # List tools
                print("\n🔄 Listing available tools...")
                tools = await session.list_tools()
                print(f"✅ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description}")
                
                # List resources
                print("\n🔄 Listing available resources...")
                resources = await session.list_resources()
                print(f"✅ Found {len(resources)} resources:")
                for resource in resources:
                    print(f"  - {resource.name}: {resource.description}")
                
                # Test a simple tool call
                print("\n🔄 Testing get_database_info tool...")
                result = await session.call_tool("get_database_info", {})
                print("✅ Database info result:")
                result_text = result[0].text if hasattr(result[0], 'text') else str(result[0])
                print(result_text[:200] + "..." if len(result_text) > 200 else result_text)
                
                print("\n🎉 All tests passed! MCP server is working correctly.")
                
    except Exception as e:
        print(f"❌ Error testing MCP server: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp_server()) 