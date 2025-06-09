#!/usr/bin/env python3
"""
Direct test of MCP server functions
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server import get_database_info, get_conversation_history, search_conversations
from loguru import logger

async def test_functions():
    """Test the MCP server functions directly."""
    
    print("🧪 Testing APE MCP Server Functions")
    print("=" * 50)
    
    # Test database info
    print("\n1️⃣ Testing get_database_info()...")
    try:
        db_info = await get_database_info()
        print("✅ Database info retrieved successfully:")
        print(db_info[:300] + "..." if len(db_info) > 300 else db_info)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test conversation history
    print("\n2️⃣ Testing get_conversation_history()...")
    try:
        history = await get_conversation_history(limit=3)
        print("✅ Conversation history retrieved successfully:")
        print(history[:300] + "..." if len(history) > 300 else history)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test search conversations
    print("\n3️⃣ Testing search_conversations()...")
    try:
        search_results = await search_conversations("test", limit=2)
        print("✅ Search completed successfully:")
        print(search_results[:300] + "..." if len(search_results) > 300 else search_results)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n🎉 Function tests completed!")

if __name__ == "__main__":
    asyncio.run(test_functions()) 