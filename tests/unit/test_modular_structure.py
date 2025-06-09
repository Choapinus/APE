#!/usr/bin/env python3
"""
Tests for the modular APE MCP server structure.
"""

import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch

# Import the modular components
from ape.mcp.session_manager import SessionManager, get_session_manager
from ape.mcp.tool_executor import ToolExecutor
from ape.mcp.implementations import (
    get_conversation_history_impl,
    get_database_info_impl,
    search_conversations_impl
)
from ape.mcp.server import create_mcp_server


class TestSessionManager:
    """Test the SessionManager class."""
    
    def test_session_manager_singleton(self):
        """Test that get_session_manager returns the same instance."""
        manager1 = get_session_manager()
        manager2 = get_session_manager()
        assert manager1 is manager2

    @patch('sqlite3.connect')
    def test_get_all_sessions(self, mock_connect):
        """Test getting all sessions."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("session1", 5, "2024-01-01", "2024-01-02"),
            ("session2", 3, "2024-01-03", "2024-01-04")
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        manager = SessionManager()
        sessions = manager.get_all_sessions()
        
        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "session1"
        assert sessions[0]["message_count"] == 5


class TestToolExecutor:
    """Test the ToolExecutor class."""
    
    def test_extract_search_query(self):
        """Test search query extraction."""
        # Test basic patterns  
        assert ToolExecutor.extract_search_query("search for hello world") == "hello world"
        assert ToolExecutor.extract_search_query("find something important") == "something important"
        assert ToolExecutor.extract_search_query("look for test data") == "test data"
        
        # Test with cleaning
        assert ToolExecutor.extract_search_query("search for hello in conversations") == "hello"
        
        # Test no match
        assert ToolExecutor.extract_search_query("just a regular message") is None

    @pytest.mark.asyncio
    async def test_should_use_tool_history(self):
        """Test tool detection for history requests."""
        test_cases = [
            ("get the last 5 messages", "history"),
            ("show me recent conversations", "history"),
            ("conversation history", "history"),
            ("interactions from the database", "history"),
        ]
        
        for message, expected_tool in test_cases:
            result = await ToolExecutor.should_use_tool(message)
            assert result is not None
            assert result["tool"] == expected_tool
            assert result["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_should_use_tool_search(self):
        """Test tool detection for search requests."""
        test_cases = [
            ("search for hello", "search"),
            ("find something", "search"),
            ("look for test", "search"),
        ]
        
        for message, expected_tool in test_cases:
            result = await ToolExecutor.should_use_tool(message)
            assert result is not None
            assert result["tool"] == expected_tool
            assert result["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_should_use_tool_database(self):
        """Test tool detection for database requests."""
        test_cases = [
            ("how many total messages", "database"),
            ("database statistics", "database"),
            ("total conversations", "database"),
        ]
        
        for message, expected_tool in test_cases:
            result = await ToolExecutor.should_use_tool(message)
            assert result is not None
            assert result["tool"] == expected_tool
            assert result["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_should_not_trigger_on_formatting(self):
        """Test that formatting requests don't trigger tools."""
        test_cases = [
            "present that information as a markdown table",
            "format the data nicely",
            "show that in a table",
        ]
        
        for message in test_cases:
            result = await ToolExecutor.should_use_tool(message)
            assert result is None


class TestImplementations:
    """Test the implementation functions."""
    
    @pytest.mark.asyncio
    @patch('sqlite3.connect')
    async def test_get_conversation_history_impl(self, mock_connect):
        """Test conversation history implementation."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("session1", "user", "Hello", "2024-01-01 10:00:00"),
            ("session1", "assistant", "Hi there!", "2024-01-01 10:01:00")
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        result = await get_conversation_history_impl("session1", 10)
        data = json.loads(result)
        
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "Hello"

    @pytest.mark.asyncio  
    @patch('sqlite3.connect')
    async def test_get_database_info_impl(self, mock_connect):
        """Test database info implementation."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ("CREATE TABLE history...",),  # schema
            (100,),  # total messages
            (5,),    # total sessions
        ]
        mock_cursor.fetchall.side_effect = [
            [("user", 60), ("assistant", 40)],  # role counts
            [("2024-01-01", 10), ("2024-01-02", 15)]  # recent activity
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        result = await get_database_info_impl()
        data = json.loads(result)
        
        assert data["statistics"]["total_messages"] == 100
        assert data["statistics"]["total_sessions"] == 5
        assert "user" in data["statistics"]["messages_by_role"]

    @pytest.mark.asyncio
    @patch('sqlite3.connect')  
    async def test_search_conversations_impl(self, mock_connect):
        """Test search implementation."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("session1", "user", "Hello world test", "2024-01-01 10:00:00")
        ]
        mock_connect.return_value.cursor.return_value = mock_cursor
        
        result = await search_conversations_impl("hello", 5)
        data = json.loads(result)
        
        assert len(data) == 1
        assert data[0]["content"] == "Hello world test"
        assert data[0]["relevance"] == "Contains: hello"


class TestMCPServer:
    """Test the MCP server creation and configuration."""
    
    def test_create_mcp_server(self):
        """Test that the MCP server is created properly."""
        server = create_mcp_server()
        
        # Verify it's a FastMCP instance
        from fastmcp import FastMCP
        assert isinstance(server, FastMCP)
        
        # Check that tools are registered (this is a basic check)
        # The actual tools are registered internally by the FastMCP decorators


@pytest.mark.asyncio
async def test_integration_workflow():
    """Test a complete integration workflow."""
    # Test tool detection -> execution workflow
    executor = ToolExecutor()
    
    # Test history request
    message = "get the last 5 interactions from the database"
    tool_info = await executor.should_use_tool(message)
    assert tool_info is not None
    assert tool_info["tool"] == "history"
    
    # Test search request  
    message = "search for hello world"
    tool_info = await executor.should_use_tool(message)
    assert tool_info is not None
    assert tool_info["tool"] == "search"
    assert tool_info["query"] == "hello world"
    
    # Test conversational message (should not trigger tools)
    message = "can you present that information as a markdown table?"
    tool_info = await executor.should_use_tool(message)
    assert tool_info is None


if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running APE MCP Modular Structure Tests...")
    
    # Test SessionManager
    print("✅ Testing SessionManager singleton...")
    test_sm = TestSessionManager()
    test_sm.test_session_manager_singleton()
    
    # Test ToolExecutor
    print("✅ Testing ToolExecutor query extraction...")
    test_te = TestToolExecutor()
    test_te.test_extract_search_query()
    
    # Test async functions
    async def run_async_tests():
        print("✅ Testing tool detection...")
        await test_te.test_should_use_tool_history()
        await test_te.test_should_use_tool_search() 
        await test_te.test_should_use_tool_database()
        await test_te.test_should_not_trigger_on_formatting()
        
        print("✅ Testing integration workflow...")
        await test_integration_workflow()
    
    # Run async tests
    asyncio.run(run_async_tests())
    
    print("🎉 All modular structure tests passed!")
    print("\n📊 **MODULARIZATION SUMMARY:**")
    print("• SessionManager: Database operations")
    print("• ToolExecutor: Tool detection & execution logic")
    print("• Implementations: Core tool functions")
    print("• Server: MCP server configuration")
    print("• Tests: Organized in tests/unit/") 