#!/usr/bin/env python3
"""
Test the chat functionality with Ollama
"""

import asyncio
import sys
import os
import uuid

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server import chat_with_llm
from loguru import logger

async def test_chat():
    """Test the chat_with_llm function."""
    
    print("🗣️ Testing APE Chat Functionality")
    print("=" * 50)
    
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"
    
    # Test basic chat
    print("\n1️⃣ Testing basic chat without history...")
    try:
        response = await chat_with_llm(
            message="Hello! What's 2+2?",
            session_id=session_id,
            include_history=False
        )
        print("✅ Chat response received:")
        print(f"Response: {response[:150]}..." if len(response) > 150 else f"Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Test chat with history
    print("\n2️⃣ Testing chat with conversation history...")
    try:
        response = await chat_with_llm(
            message="What was my previous question?",
            session_id=session_id,
            include_history=True
        )
        print("✅ Chat with history response:")
        print(f"Response: {response[:150]}..." if len(response) > 150 else f"Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test another message in the same session
    print("\n3️⃣ Testing continued conversation...")
    try:
        response = await chat_with_llm(
            message="Can you solve a different math problem: 10 * 7?",
            session_id=session_id,
            include_history=True
        )
        print("✅ Continued conversation response:")
        print(f"Response: {response[:150]}..." if len(response) > 150 else f"Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print(f"\n🎉 Chat testing completed for session: {session_id}")

if __name__ == "__main__":
    asyncio.run(test_chat()) 