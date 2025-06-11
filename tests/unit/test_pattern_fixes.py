#!/usr/bin/env python3
"""
Test the LLM's ability to understand and handle different types of requests.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server_refined import ToolExecutor, _chat_with_llm_impl
from loguru import logger

async def test_llm_understanding():
    """Test the LLM's ability to understand and handle different types of requests."""
    print('🤖 Testing LLM Understanding')
    print('=' * 50)
    
    # Test various user intents without hardcoding expected behaviors
    test_cases = [
        "I need information about our previous conversations",
        "Could you help me understand what's in the database?",
        "Let's analyze some of our chat history",
        "I'm looking for specific messages",
        "What capabilities do you have?",
        "Can you tell me more about how you work?",
        "I need help with searching through our discussions"
    ]
    
    for message in test_cases:
        print(f'\n💬 Testing: "{message}"')
        
        try:
            result = await _chat_with_llm_impl(message, f'test-llm-{abs(hash(message))}', False)
            
            # Display result and let human testers evaluate
            print(f'📤 Result preview: {result[:200]}...' if len(result) > 200 else result)
            print('✅ LLM provided a response')
            
        except Exception as e:
            print(f'❌ Error: {e}')

async def test_context_awareness():
    """Test the LLM's ability to maintain context and use previous information."""
    print('\n🧠 Testing Context Awareness')
    print('=' * 50)
    
    # Simulate a conversation flow
    conversation = [
        "What can you tell me about our chat history?",
        "Can you analyze that information differently?",
        "I'd like to focus on a specific part of that data",
        "Could you help me understand those results better?",
        "Let's try a different approach to this"
    ]
    
    session_id = 'test-context-awareness'
    
    for i, message in enumerate(conversation):
        print(f'\n💬 Message {i+1}: "{message}"')
        
        try:
            result = await _chat_with_llm_impl(message, session_id, True)  # Include history
            print(f'📤 Result preview: {result[:200]}...' if len(result) > 200 else result)
            print('✅ Response received')
            
        except Exception as e:
            print(f'❌ Error: {e}')

if __name__ == "__main__":
    asyncio.run(test_llm_understanding())
    asyncio.run(test_context_awareness()) 