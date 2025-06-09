#!/usr/bin/env python3
"""
Test the enhanced chat functionality with tool usage
"""

import asyncio
import sys
import os
import uuid

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server import chat_with_llm

async def test_enhanced_chat():
    """Test the enhanced chat with tool detection."""
    
    print("🧪 Testing Enhanced Chat with Tool Usage")
    print("=" * 60)
    
    session_id = f"test-enhanced-{uuid.uuid4().hex[:8]}"
    
    # Test 1: Regular chat
    print("\n1️⃣ Testing regular chat...")
    response = await chat_with_llm(
        message="Hello! How are you?",
        session_id=session_id,
        include_history=False
    )
    print(f"Response: {response[:100]}...")
    
    # Test 2: Ask about tools/capabilities
    print("\n2️⃣ Testing capability inquiry...")
    response = await chat_with_llm(
        message="What tools do you have?",
        session_id=session_id,
        include_history=True
    )
    print(f"Response: {response[:150]}...")
    
    # Test 3: Try to trigger search tool
    print("\n3️⃣ Testing search trigger...")
    response = await chat_with_llm(
        message="Search for conversations about hello",
        session_id=session_id,
        include_history=True
    )
    print(f"Response: {response[:150]}...")
    
    # Test 4: Try to trigger history tool
    print("\n4️⃣ Testing history trigger...")
    response = await chat_with_llm(
        message="Show me conversation history",
        session_id=session_id,
        include_history=True
    )
    print(f"Response: {response[:150]}...")
    
    print(f"\n🎉 Enhanced chat testing completed for session: {session_id}")

if __name__ == "__main__":
    asyncio.run(test_enhanced_chat()) 