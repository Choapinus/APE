#!/usr/bin/env python3
"""
APE MCP Server - Advanced Prompt Engine as Model Context Protocol Server

This replaces the complex FastAPI + custom ReAct implementation with a 
standard MCP server that handles tool execution cleanly.
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Sequence

import mcp.types as types
from mcp.server.fastmcp import FastMCP

from ape.config import LLM_MODEL, OLLAMA_HOST
from ape.session import get_session_manager
from loguru import logger

# Initialize the FastMCP server
mcp = FastMCP("ape-mcp-server")

# Database path for session storage
DB_PATH = "ape/sessions.db"


@mcp.tool()
async def get_conversation_history(session_id: str = None, limit: int = 10) -> str:
    """
    Retrieve recent conversation history from the database.
    
    Args:
        session_id: Session ID to get history for (optional)
        limit: Number of recent messages to retrieve (default: 10)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if session_id:
            query = """
                SELECT session_id, role, content, timestamp 
                FROM history 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(query, (session_id, limit))
        else:
            query = """
                SELECT session_id, role, content, timestamp 
                FROM history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(query, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "No conversation history found."
        
        history = []
        for session_id, role, content, timestamp in reversed(rows):
            history.append({
                "session_id": session_id,
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        
        return json.dumps(history, indent=2)
        
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return f"Error retrieving history: {str(e)}"


@mcp.tool()
async def get_database_info() -> str:
    """
    Get information about the conversation database schema and statistics.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='history';")
        schema = cursor.fetchone()
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM history;")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM history;")
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT role, COUNT(*) FROM history GROUP BY role;")
        role_counts = dict(cursor.fetchall())
        
        conn.close()
        
        info = {
            "database_path": DB_PATH,
            "schema": schema[0] if schema else "No schema found",
            "statistics": {
                "total_messages": total_messages,
                "total_sessions": total_sessions,
                "messages_by_role": role_counts
            }
        }
        
        return json.dumps(info, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return f"Error getting database info: {str(e)}"


@mcp.tool()
async def search_conversations(query: str, limit: int = 5) -> str:
    """
    Search through conversation history using text matching.
    
    Args:
        query: Text to search for in conversation content
        limit: Maximum number of results to return (default: 5)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Simple text search in content
        sql_query = """
            SELECT session_id, role, content, timestamp 
            FROM history 
            WHERE content LIKE ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        
        search_term = f"%{query}%"
        cursor.execute(sql_query, (search_term, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"No conversations found matching: {query}"
        
        results = []
        for session_id, role, content, timestamp in rows:
            results.append({
                "session_id": session_id,
                "role": role,
                "content": content[:200] + "..." if len(content) > 200 else content,
                "timestamp": timestamp
            })
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        return f"Error searching conversations: {str(e)}"


async def _execute_tool_if_needed(message: str, session_id: str = None) -> str:
    """Check if the user message requires tool execution and do it."""
    message_lower = message.lower()
    
    # Tool detection patterns
    if any(keyword in message_lower for keyword in ["search", "find", "look for"]) and any(keyword in message_lower for keyword in ["conversation", "message", "chat", "history"]):
        # Extract search query
        for phrase in ["search for", "find", "look for"]:
            if phrase in message_lower:
                query = message_lower.split(phrase)[-1].strip()
                if query:
                    results = await search_conversations(query, 5)
                    return f"🔍 **Search Results for '{query}':**\n{results}\n\nIs there anything specific from these results you'd like to know more about?"
    
    elif any(keyword in message_lower for keyword in ["history", "past", "previous", "earlier"]) and any(keyword in message_lower for keyword in ["conversation", "message", "chat"]):
        # Get conversation history
        limit = 10
        if session_id:
            results = await get_conversation_history(session_id, limit)
        else:
            results = await get_conversation_history(None, limit)
        return f"📚 **Recent Conversation History:**\n{results}\n\nWould you like to see more or search for something specific?"
    
    elif any(keyword in message_lower for keyword in ["database", "stats", "statistics", "data", "info"]):
        # Get database info
        results = await get_database_info()
        return f"🗄️ **Database Information:**\n{results}\n\nIs there anything specific about the data you'd like to know?"
    
    return None  # No tool needed


@mcp.tool()
async def chat_with_llm(message: str, session_id: str = None, include_history: bool = True) -> str:
    """
    Chat with the LLM with intelligent tool usage capabilities.
    
    Args:
        message: Message to send to the LLM
        session_id: Session ID for conversation context (optional)
        include_history: Whether to include conversation history (default: True)
    """
    try:
        import httpx
        from ollama import Client
        
        # First, check if this message requires tool execution
        tool_result = await _execute_tool_if_needed(message, session_id)
        if tool_result:
            # Save the tool interaction
            if session_id:
                session_manager = get_session_manager()
                history = session_manager.get_history(session_id) if include_history else []
                history.extend([
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": tool_result}
                ])
                session_manager.save_messages(session_id, history)
            return tool_result
        
        # Initialize Ollama client for regular chat
        client = Client(host=OLLAMA_HOST)
        
        # Enhanced system prompt with tool awareness
        system_prompt = """You are APE (Advanced Prompt Engine), an AI assistant that helps users manage their conversation history. 

You have access to conversation management tools:
• Search through conversation history
• Retrieve past conversations  
• Get database statistics

When users ask about:
- "What did we talk about..." → You can search their conversation history
- "Show me my conversations" → You can retrieve their conversation history
- "How many messages..." → You can get database statistics

Be helpful and mention these capabilities when relevant. If someone asks about your tools or capabilities, tell them about these conversation management features."""

        # Prepare messages
        messages = [{"role": "system", "content": system_prompt}]
        
        if include_history and session_id:
            # Get conversation history for context
            session_manager = get_session_manager()
            history = session_manager.get_history(session_id)
            
            # Add recent history (last 10 messages, excluding system)
            for msg in history[-10:]:
                if msg["role"] != "system":
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # Call LLM
        response = client.chat(
            model=LLM_MODEL,
            messages=messages
        )
        
        assistant_response = response['message']['content']
        
        # Save to session if session_id provided
        if session_id:
            session_manager = get_session_manager()
            # Get existing history and add new messages
            conversation_history = session_manager.get_history(session_id) if include_history else []
            conversation_history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": assistant_response}
            ])
            session_manager.save_messages(session_id, conversation_history)
        
        return assistant_response
        
    except Exception as e:
        logger.error(f"Error communicating with LLM: {e}")
        return f"Error communicating with LLM: {str(e)}"


@mcp.resource("conversation://sessions")
async def get_all_sessions() -> str:
    """
    Get overview of all conversation sessions.
    """
    try:
        session_manager = get_session_manager()
        sessions = session_manager.get_all_sessions()
        return json.dumps(sessions, indent=2)
    except Exception as e:
        logger.error(f"Error getting all sessions: {e}")
        return f"Error getting all sessions: {str(e)}"


@mcp.resource("conversation://recent")
async def get_recent_messages() -> str:
    """
    Get most recent conversation messages.
    """
    try:
        return await get_conversation_history(limit=20)
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return f"Error getting recent messages: {str(e)}"


if __name__ == "__main__":
    # Setup logging
    logger.add("logs/mcp_server.log", rotation="1 day", retention="7 days")
    logger.info("Starting APE MCP Server")
    
    # The FastMCP server will be automatically run by the mcp dev command
    print("APE MCP Server is ready!") 