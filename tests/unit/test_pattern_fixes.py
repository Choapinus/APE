#!/usr/bin/env python3
"""
Test the pattern recognition fixes for the "from database" issue.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_server_refined import ToolExecutor, _chat_with_llm_impl
from loguru import logger

async def test_pattern_fixes():
    """Test the problematic pattern recognition cases."""
    print('🔧 Testing Pattern Recognition Fixes')
    print('=' * 50)
    
    # Test the problematic cases
    test_cases = [
        ('get the last 5 interactions from the database', 'Should trigger HISTORY tool'),
        ('show me database statistics', 'Should trigger DATABASE tool'),
        ('how many messages are there?', 'Should trigger DATABASE tool'),
        ('last interactions', 'Should trigger HISTORY tool'),
        ('database info', 'Should trigger DATABASE tool'),
        ('messages from the database', 'Should trigger HISTORY tool'),
        ('show the last conversations', 'Should trigger HISTORY tool'),
        ('total message count', 'Should trigger DATABASE tool'),
    ]
    
    for message, expected in test_cases:
        print(f'\n💬 "{message}"')
        print(f'📋 Expected: {expected}')
        
        tool_info = await ToolExecutor.should_use_tool(message, 'test-session')
        if tool_info:
            tool_type = tool_info['tool']
            confidence = tool_info.get('confidence', 'unknown')
            print(f'🔧 Detected: {tool_type.upper()} tool (confidence: {confidence})')
            
            expected_tool = expected.lower().split('trigger ')[1].split(' tool')[0]
            if tool_type == expected_tool:
                print('✅ CORRECT!')
            else:
                print(f'❌ WRONG! Expected {expected_tool}, got {tool_type}')
        else:
            print('⚪ No tool detected')

async def test_real_execution():
    """Test actual tool execution with the fixed patterns."""
    print('\n🎯 Testing Real Tool Execution')
    print('=' * 50)
    
    scenarios = [
        ('get the last 5 interactions from the database', 'Should show conversation history'),
        ('how many total messages are stored?', 'Should show database statistics'),
    ]
    
    for message, expected in scenarios:
        print(f'\n💬 "{message}"')
        print(f'📋 Expected: {expected}')
        
        try:
            result = await _chat_with_llm_impl(message, f'test-fix-{abs(hash(message))}', False)
            
            if '📚' in result and 'Tool: get_conversation_history executed' in result:
                print('✅ History tool executed correctly!')
            elif '🗄️' in result and 'Tool: get_database_info executed' in result:
                print('✅ Database tool executed correctly!')
            elif 'Tool:' in result:
                print('⚠️ Some tool executed, check if correct')
            else:
                print('💬 LLM response (no tool)')
                
        except Exception as e:
            print(f'❌ Error: {e}')

async def main():
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    
    await test_pattern_fixes()
    await test_real_execution()
    
    print('\n🎉 Pattern fix testing completed!')
    print('\nIf the tests show "CORRECT!" for most cases, the fixes are working!')

if __name__ == "__main__":
    asyncio.run(main()) 