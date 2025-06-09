#!/usr/bin/env python3
"""Test script for MCP server functionality."""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp():
    """Test the MCP server and tools."""
    try:
        server_params = StdioServerParameters(
            command='python', 
            args=['mcp_server.py'], 
            env=None
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                tools_result = await session.list_tools()
                print('🔧 Available MCP tools:')
                
                for tool in tools_result.tools:
                    print(f'- {tool.name}: {tool.description}')
                
                print('\n🗄️ Testing get_database_info tool:')
                try:
                    result = await session.call_tool('get_database_info', {})
                    if result.content:
                        print("Database info:")
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(content.text[:500] + "...")
                    else:
                        print("No content returned")
                
                    print('\n📚 Testing get_conversation_history tool:')
                    result = await session.call_tool('get_conversation_history', {"limit": 3})
                    if result.content:
                        print("Conversation history:")
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(content.text[:300] + "...")
                    else:
                        print("No conversation history")
                        
                except Exception as e:
                    print(f"Error calling tool: {e}")
                    import traceback
                    traceback.print_exc()
                    
    except Exception as e:
        print(f"❌ Error testing MCP: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp()) 