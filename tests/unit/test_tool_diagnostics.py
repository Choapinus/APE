#!/usr/bin/env python3
"""
Diagnostic testing script for APE MCP tools.
This script tests each tool individually to identify hallucination vs actual execution.
"""

import asyncio
import sys
import os
import json

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server import (
    get_conversation_history, 
    get_database_info, 
    search_conversations,
    chat_with_llm,
    _execute_tool_if_needed
)
from loguru import logger

async def test_database_info():
    """Test the database info tool directly."""
    print("🗄️ Testing get_database_info()...")
    try:
        result = await get_database_info()
        print("✅ Database info result:")
        print(result)
        print()
        
        # Parse and validate the result
        data = json.loads(result)
        total_messages = data["statistics"]["total_messages"]
        print(f"📊 Total messages in database: {total_messages}")
        return True
    except Exception as e:
        print(f"❌ Database info test failed: {e}")
        return False

async def test_search_functionality():
    """Test the search tool with known queries."""
    print("🔍 Testing search_conversations()...")
    
    # Test 1: Search for a term that might actually exist
    print("Test 1: Searching for 'thinking'...")
    try:
        result = await search_conversations("thinking", 3)
        print("✅ Search result:")
        print(result)
        print()
        
        # Parse result
        data = json.loads(result)
        if isinstance(data, list):
            print(f"📊 Found {len(data)} actual matches")
        else:
            print(f"📊 Result type: {type(data)}")
        
    except Exception as e:
        print(f"❌ Search test 1 failed: {e}")
    
    # Test 2: Search for something that definitely doesn't exist
    print("Test 2: Searching for 'nonexistentterm12345'...")
    try:
        result = await search_conversations("nonexistentterm12345", 3)
        print("✅ Search result:")
        print(result)
        print()
        
    except Exception as e:
        print(f"❌ Search test 2 failed: {e}")

async def test_conversation_history():
    """Test conversation history retrieval."""
    print("📚 Testing get_conversation_history()...")
    try:
        result = await get_conversation_history(None, 5)  # Get last 5 messages
        print("✅ History result:")
        print(result)
        print()
        
        # Parse result
        data = json.loads(result)
        if isinstance(data, list):
            print(f"📊 Retrieved {len(data)} messages")
        else:
            print(f"📊 Result type: {type(data)}")
            
    except Exception as e:
        print(f"❌ History test failed: {e}")

async def test_tool_auto_detection():
    """Test the automatic tool detection patterns."""
    print("🤖 Testing tool auto-detection patterns...")
    
    test_cases = [
        "search for weather",
        "show me my conversation history", 
        "get database information",
        "can you execute another tool?",
        "search conversations for thinking",
        "what's in the database?",
        "clean the database",
        "hello there"
    ]
    
    for test_message in test_cases:
        print(f"\nTesting: '{test_message}'")
        try:
            result = await _execute_tool_if_needed(test_message, "test-session")
            if result:
                print(f"✅ Tool executed: {result[:100]}...")
            else:
                print("⚪ No tool triggered")
        except Exception as e:
            print(f"❌ Error: {e}")

async def test_chat_with_search():
    """Test the full chat_with_llm function with search queries."""
    print("💬 Testing chat_with_llm with search queries...")
    
    test_queries = [
        "search for weather", 
        "find messages about database",
        "show me database stats"
    ]
    
    for query in test_queries:
        print(f"\nTesting chat query: '{query}'")
        try:
            result = await chat_with_llm(query, "test-diagnostic-session", include_history=False)
            print(f"✅ Chat result: {result[:200]}...")
            
            # Check if this looks like a hallucination
            if "weather" in query and "temperature" in result and "°C" in result:
                print("⚠️  WARNING: This looks like hallucinated weather data!")
            elif "weather" in query and len(result) > 100:
                print("⚠️  WARNING: Possible hallucination - too detailed for no results")
                
        except Exception as e:
            print(f"❌ Chat test failed: {e}")

async def test_llm_tool_selection():
    """Test the LLM's ability to select and use appropriate tools."""
    print("🤖 Testing LLM tool selection...")
    
    test_cases = [
        "I'd like to understand our conversation history",
        "Help me find specific information in our chats",
        "What kind of data do we have stored?",
        "Can you analyze our previous discussions?",
        "I need to search through our past conversations",
        "Tell me about the system's capabilities",
        "How can you help me with information retrieval?"
    ]
    
    for test_message in test_cases:
        print(f"\nTesting: '{test_message}'")
        try:
            result = await chat_with_llm(test_message, "test-diagnostic-session", include_history=False)
            print(f"Response preview: {result[:200]}...")
            
            # Note: We don't predict what tools should be used, we let the LLM decide
            if "Tool executed:" in result:
                print("✅ LLM chose to use a tool")
            else:
                print("✅ LLM provided direct response")
        except Exception as e:
            print(f"❌ Error: {e}")

async def test_llm_context_handling():
    """Test the LLM's ability to handle context and make appropriate decisions."""
    print("🧠 Testing LLM context handling...")
    
    # Simulate a conversation that builds context
    conversation = [
        "What information do we have available?",
        "Can you analyze that data differently?",
        "Let's focus on specific parts of that information",
        "How does that compare to our previous discussions?",
        "Can you summarize what we've found?"
    ]
    
    session_id = "test-context-session"
    
    for i, query in enumerate(conversation):
        print(f"\nStep {i+1}: '{query}'")
        try:
            result = await chat_with_llm(query, session_id, include_history=True)
            print(f"Response preview: {result[:200]}...")
            
            # We're interested in how the LLM builds on context
            if i > 0:
                print("Context handling check:")
                if "previous" in result.lower() or "earlier" in result.lower():
                    print("✅ LLM referenced previous context")
                else:
                    print("ℹ️ New information provided")
        except Exception as e:
            print(f"❌ Error: {e}")

async def test_llm_capability_discovery():
    """Test the LLM's ability to discover and utilize available capabilities."""
    print("🔍 Testing LLM capability discovery...")
    
    discovery_queries = [
        "What can you help me with?",
        "Show me your capabilities",
        "How can you assist me with information?",
        "What tools do you have access to?",
        "Explain how you can help me search and analyze data"
    ]
    
    for query in discovery_queries:
        print(f"\nTesting: '{query}'")
        try:
            result = await chat_with_llm(query, "test-discovery-session", include_history=False)
            print(f"Response preview: {result[:200]}...")
            
            # Check if the LLM demonstrates understanding of its capabilities
            if any(capability in result.lower() for capability in ["tool", "search", "database", "history", "analyze"]):
                print("✅ LLM demonstrated capability awareness")
            else:
                print("ℹ️ General response provided")
        except Exception as e:
            print(f"❌ Error: {e}")

async def main():
    """Run all diagnostic tests."""
    print("🔬 APE MCP Tool Diagnostics")
    print("=" * 50)
    print()
    
    # Configure minimal logging
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    
    # Run tests in sequence
    await test_database_info()
    await test_search_functionality() 
    await test_conversation_history()
    await test_tool_auto_detection()
    await test_chat_with_search()
    await test_llm_tool_selection()
    await test_llm_context_handling()
    await test_llm_capability_discovery()
    
    print("\n🏁 Diagnostic tests completed!")
    print("Review the results above to identify:")
    print("- Tools that work correctly")
    print("- Tools that hallucinate responses")
    print("- Pattern detection accuracy")
    print("- Areas needing refinement")

if __name__ == "__main__":
    asyncio.run(main()) 