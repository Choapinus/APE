#!/usr/bin/env python3
"""
Test script for the refined APE MCP implementation.
Tests the enhanced tool detection and anti-hallucination measures.
"""

import asyncio
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server_refined import (
    ToolExecutor,
    _chat_with_llm_impl,
    _search_conversations_impl
)
from loguru import logger

async def test_enhanced_search_detection():
    """Test the enhanced search query extraction."""
    print("🔍 Testing Enhanced Search Detection")
    print("=" * 50)
    
    test_cases = [
        "search for weather",
        "search conversations for thinking", 
        "find messages about database",
        "look for messages about hello",
        "search through history for error",
        "search weather",  # Short form
        "find weather",   # Different verb
        "random message",  # Should not trigger
    ]
    
    for test_case in test_cases:
        query = ToolExecutor.extract_search_query(test_case)
        print(f"'{test_case}' → Query: {query}")
    
    print()

async def test_refined_tool_execution():
    """Test the refined tool execution logic."""
    print("🛠️ Testing Refined Tool Execution")
    print("=" * 50)
    
    test_cases = [
        ("search for weather", "Should execute search tool"),
        ("search conversations for thinking", "Should execute search tool"),
        ("show me conversation history", "Should execute history tool"),
        ("get database information", "Should execute database tool"),
        ("clean the database", "Should show unsupported operation"),
        ("hello there", "Should not execute any tool"),
        ("can you execute another tool?", "Should not execute any tool"),
    ]
    
    for message, expected in test_cases:
        print(f"\nTesting: '{message}'")
        print(f"Expected: {expected}")
        
        result = await ToolExecutor.execute_tool_if_needed(message, "test-session")
        if result:
            print(f"✅ Tool executed: {result[:100]}...")
            # Check for tool execution marker
            if "*Tool:" in result:
                print("✅ Contains execution marker")
            else:
                print("⚠️ Missing execution marker")
        else:
            print("⚪ No tool executed")
    
    print()

async def test_anti_hallucination():
    """Test that the refined system prevents hallucination."""
    print("🚫 Testing Anti-Hallucination Measures")
    print("=" * 50)
    
    # Test search for non-existent data
    print("Test 1: Searching for weather (should find actual results or none)")
    result = await _search_conversations_impl("weather", 3)
    print(f"Search result: {result}")
    
    if "temperature" in result and "°C" in result:
        print("❌ HALLUCINATION DETECTED: Fake weather data present")
    else:
        print("✅ No hallucination detected")
    
    print("\nTest 2: Chat with search query (should use actual tool)")
    result = await _chat_with_llm_impl("search for weather", "test-anti-hallucination", False)
    print(f"Chat result: {result[:200]}...")
    
    if "*Tool:" in result:
        print("✅ Proper tool execution detected")
    elif "temperature" in result and "°C" in result:
        print("❌ HALLUCINATION DETECTED: Fake weather data in chat")
    else:
        print("⚠️ Unclear result - manual review needed")
    
    print()

async def test_integration_scenarios():
    """Test realistic user interaction scenarios."""
    print("🎭 Testing Integration Scenarios")
    print("=" * 50)
    
    scenarios = [
        ("search for hello", "Should find actual messages with 'hello'"),
        ("what did we talk about regarding database?", "Should search for 'database'"),
        ("show me our recent conversations", "Should show conversation history"),
        ("how many messages are in the system?", "Should show database info"),
        ("search for nonexistentterm12345", "Should return no results found"),
    ]
    
    for message, expected in scenarios:
        print(f"\nScenario: '{message}'")
        print(f"Expected: {expected}")
        
        result = await _chat_with_llm_impl(message, f"test-scenario-{hash(message)}", False)
        print(f"Result: {result[:150]}...")
        
        # Basic validation
        if "Tool:" in result:
            print("✅ Tool execution detected")
        elif len(result) > 200 and ("weather" in message or "temperature" in result):
            print("⚠️ Possible hallucination - long response to simple query")
        else:
            print("⚪ Regular chat response")
    
    print()

async def main():
    """Run all refinement tests."""
    print("🔬 APE MCP Refined Implementation Tests")
    print("=" * 60)
    print()
    
    # Configure minimal logging
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    
    # Run all tests
    await test_enhanced_search_detection()
    await test_refined_tool_execution()
    await test_anti_hallucination()
    await test_integration_scenarios()
    
    print("🏁 Refinement tests completed!")
    print("\nKey improvements to verify:")
    print("✅ Enhanced search pattern detection")
    print("✅ Clear tool execution markers")
    print("✅ Anti-hallucination system prompts")
    print("✅ Proper unsupported operation handling")
    print("✅ Improved pattern recognition accuracy")

if __name__ == "__main__":
    asyncio.run(main()) 