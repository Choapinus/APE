#!/usr/bin/env python3
"""
APE (Advanced Prompt Engine) MCP Server - Refined Version

This is a Model Context Protocol server that provides conversation management
tools with enhanced tool detection and anti-hallucination measures.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastmcp import FastMCP
from loguru import logger

# Configuration
DB_PATH = "ape/sessions.db"
LLM_MODEL = "gemma3:4b"
OLLAMA_HOST = "http://localhost:11434"

# Initialize the FastMCP server
mcp = FastMCP("APE Server - Refined")


class SessionManager:
    """Manages conversation sessions and database operations."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with the required table."""
        # Ensure the directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                images TEXT, -- JSON serialized list of base64 strings
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        """Save messages to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clear existing messages for this session
            cursor.execute("DELETE FROM history WHERE session_id = ?", (session_id,))
            
            # Insert new messages
            for msg in messages:
                cursor.execute("""
                    INSERT INTO history (session_id, role, content, images, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    msg["role"],
                    msg["content"],
                    json.dumps(msg.get("images", [])),
                    msg.get("timestamp", datetime.now().isoformat())
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving messages: {e}")
            raise
    
    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT role, content, images, timestamp
                FROM history
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            messages = []
            for role, content, images, timestamp in rows:
                msg = {
                    "role": role,
                    "content": content,
                    "timestamp": timestamp
                }
                if images:
                    msg["images"] = json.loads(images)
                messages.append(msg)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get information about all sessions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT session_id, COUNT(*) as message_count, 
                       MIN(timestamp) as first_message,
                       MAX(timestamp) as last_message
                FROM history
                GROUP BY session_id
                ORDER BY last_message DESC
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            sessions = []
            for session_id, count, first, last in rows:
                sessions.append({
                    "session_id": session_id,
                    "message_count": count,
                    "first_message": first,
                    "last_message": last
                })
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []


# Global session manager
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# Implementation functions (not decorated - for internal use)
async def _get_conversation_history_impl(session_id: str = None, limit: int = 10) -> str:
    """Implementation of get_conversation_history without MCP decoration."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if session_id:
            # Get history for specific session
            sql_query = """
                SELECT session_id, role, content, timestamp 
                FROM history 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(sql_query, (session_id, limit))
        else:
            # Get recent messages across all sessions
            sql_query = """
                SELECT session_id, role, content, timestamp 
                FROM history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(sql_query, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "No conversation history found."
        
        # Format the results as JSON
        messages = []
        for session_id_db, role, content, timestamp in rows:
            messages.append({
                "session_id": session_id_db,
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        
        return json.dumps(messages, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return f"Error getting conversation history: {str(e)}"


async def _get_database_info_impl() -> str:
    """Implementation of get_database_info without MCP decoration."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='history'")
        schema_result = cursor.fetchone()
        schema = schema_result[0] if schema_result else "No schema found"
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM history")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM history")
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT role, COUNT(*) FROM history GROUP BY role")
        role_counts = dict(cursor.fetchall())
        
        conn.close()
        
        info = {
            "database_path": DB_PATH,
            "schema": schema,
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


async def _search_conversations_impl(query: str, limit: int = 5) -> str:
    """Implementation of search_conversations without MCP decoration."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Use LIKE for case-insensitive search
        search_pattern = f"%{query}%"
        sql_query = """
            SELECT session_id, role, content, timestamp 
            FROM history 
            WHERE content LIKE ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        
        cursor.execute(sql_query, (search_pattern, limit))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"No conversations found matching: {query}"
        
        # Format results
        results = []
        for session_id, role, content, timestamp in rows:
            # Truncate long content for readability
            content_preview = content[:150] + "..." if len(content) > 150 else content
            
            results.append({
                "session_id": session_id,
                "role": role,
                "content": content_preview,
                "timestamp": timestamp
            })
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        return f"Error searching conversations: {str(e)}"


@mcp.tool()
async def get_conversation_history(session_id: str = None, limit: int = 10) -> str:
    """
    Retrieve conversation history for analysis and context.
    
    Args:
        session_id: Session ID to get history for (optional, gets recent messages if None)
        limit: Maximum number of messages to return (default: 10)
    """
    return await _get_conversation_history_impl(session_id, limit)


@mcp.tool()
async def get_database_info() -> str:
    """
    Get detailed information about the conversation database.
    """
    return await _get_database_info_impl()


@mcp.tool()
async def search_conversations(query: str, limit: int = 5) -> str:
    """
    Search through conversation history using text matching.
    
    Args:
        query: Text to search for in conversation content
        limit: Maximum number of results to return (default: 5)
    """
    return await _search_conversations_impl(query, limit)


class ToolExecutor:
    """Enhanced tool execution with proper pattern detection and anti-hallucination."""
    
    @staticmethod
    def extract_search_query(message: str) -> Optional[str]:
        """Extract search query from user message."""
        message_lower = message.lower()
        
        # More specific search patterns
        search_phrases = [
            "search for ",
            "search conversations for ",
            "find messages about ",
            "find conversations about ",
            "look for messages about ",
            "search through history for "
        ]
        
        for phrase in search_phrases:
            if phrase in message_lower:
                # Extract everything after the phrase
                query = message_lower.split(phrase, 1)[1].strip()
                # Remove common trailing words
                query = query.replace(" please", "").replace(" in conversations", "")
                return query
        
        # Pattern: "search" + "weather" (without specific connectors)
        if "search" in message_lower and len(message.split()) <= 4:
            words = message_lower.split()
            if "search" in words:
                search_idx = words.index("search")
                if search_idx < len(words) - 1:
                    # Take the next word(s) as query
                    query_words = words[search_idx + 1:]
                    # Filter out common words
                    query_words = [w for w in query_words if w not in ["for", "about", "through", "conversations"]]
                    if query_words:
                        return " ".join(query_words)
        
        return None
    
    @staticmethod
    async def should_use_tool(message: str, session_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Intelligent tool detection that considers context and user intent.
        Returns tool info if needed, None otherwise.
        """
        message_lower = message.lower().strip()
        
        # 1. Unsupported operations (always block these)
        unsupported_keywords = ["clean", "delete", "remove", "clear", "reset", "drop", "modify", "update", "insert"]
        if any(keyword in message_lower for keyword in unsupported_keywords) and ("database" in message_lower or "conversation" in message_lower):
            return {
                "tool": "unsupported",
                "reason": "Data modification requested",
                "response": "⚠️ **Unsupported Operation**: I don't have tools to modify or clean the database. I can only read and search through the existing conversation data.\n\n*Available operations: search, view history, get database info*"
            }
        
        # 2. Explicit search requests (high confidence)
        search_query = ToolExecutor.extract_search_query(message)
        if search_query and len(search_query) > 2:  # Ensure meaningful query
            return {
                "tool": "search",
                "query": search_query,
                "confidence": "high"
            }
        
        # 3. History requests (prioritized patterns - check BEFORE database patterns)
        history_indicators = [
            # Explicit history requests
            "show conversation history", "get conversation history", "recent conversations",
            "conversation history", "chat history", "our previous messages",
            # Database retrieval requests (these want DATA, not STATS)
            "interactions from the database", "messages from the database", 
            "conversations from the database", "last interactions", "recent interactions",
            "last messages", "previous interactions", "get the last", "show the last"
        ]
        if any(indicator in message_lower for indicator in history_indicators):
            return {
                "tool": "history",
                "confidence": "high"
            }
        
        # 4. Database statistics requests (check AFTER history patterns)
        stats_indicators = [
            "database statistics", "database info", "database stats",
            "how many messages", "total messages", "message count",
            "statistics about", "stats about", "info about the database"
        ]
        if any(indicator in message_lower for indicator in stats_indicators):
            return {
                "tool": "database",
                "confidence": "medium"
            }
        
        # 5. Context-sensitive detection (low confidence)
        # Only trigger for very specific, unambiguous requests
        if message_lower in ["search", "history", "stats", "database"]:
            if "search" in message_lower:
                return {"tool": "search", "query": "", "confidence": "low"}
            elif "history" in message_lower:
                return {"tool": "history", "confidence": "low"}
            elif message_lower in ["stats", "database"]:
                return {"tool": "database", "confidence": "low"}
        
        return None  # Let LLM handle it
    
    @staticmethod
    async def execute_tool_if_needed(message: str, session_id: str = None) -> Optional[str]:
        """
        Execute tools only when there's high confidence they're needed.
        """
        tool_info = await ToolExecutor.should_use_tool(message, session_id)
        
        if not tool_info:
            return None
        
        tool_type = tool_info["tool"]
        confidence = tool_info.get("confidence", "medium")
        
        # Execute high confidence tools immediately, medium confidence for database/search
        if confidence == "low":
            return None
        elif confidence == "medium" and tool_type not in ["database", "search"]:
            return None
        
        if tool_type == "unsupported":
            logger.info(f"TOOL EXECUTION: Unsupported operation detected")
            return tool_info["response"]
        
        elif tool_type == "search":
            query = tool_info["query"]
            logger.info(f"TOOL EXECUTION: Searching for '{query}'")
            results = await _search_conversations_impl(query, 5)
            return f"🔍 **Search Results for '{query}':**\n{results}\n\n*Tool: search_conversations executed*"
        
        elif tool_type == "history":
            logger.info(f"TOOL EXECUTION: Getting conversation history")
            limit = 10
            if session_id:
                results = await _get_conversation_history_impl(session_id, limit)
            else:
                results = await _get_conversation_history_impl(None, limit)
            return f"📚 **Recent Conversation History:**\n{results}\n\n*Tool: get_conversation_history executed*"
        
        elif tool_type == "database":
            logger.info(f"TOOL EXECUTION: Getting database information")
            results = await _get_database_info_impl()
            return f"🗄️ **Database Information:**\n{results}\n\n*Tool: get_database_info executed*"
        
        return None


async def _chat_with_llm_impl(message: str, session_id: str = None, include_history: bool = True) -> str:
    """Implementation of chat_with_llm without MCP decoration."""
    try:
        import httpx
        from ollama import Client
        
        # First, check if this message requires tool execution
        tool_result = await ToolExecutor.execute_tool_if_needed(message, session_id)
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
        
        # Enhanced system prompt with tool awareness and intelligent decision making
        system_prompt = """You are APE (Advanced Prompt Engine), an AI assistant that helps users manage their conversation history.

CORE CAPABILITIES:
🔍 Search conversations - Find specific messages using keywords
📚 View history - Show recent conversation messages  
🗄️ Database info - Get statistics about stored conversations

INTELLIGENT TOOL USAGE:
- Tools are automatically triggered for explicit requests like "search for X" or "show history"
- For ambiguous requests, engage in conversation and offer to use tools if helpful
- When users ask for formatting or analysis of existing data, work with what's available
- If you need fresh data, suggest specific tool usage

CRITICAL RULES:
1. NEVER fabricate data about conversations, weather, or anything else
2. Use conversation context - if data was just retrieved, work with it instead of re-fetching
3. When asked to format/present existing information differently, do so without calling tools
4. Be conversational and helpful, not just a tool-calling robot
5. If unsure whether to use a tool, ask the user what they prefer

EXAMPLE BEHAVIORS:
- "present as markdown table" → Format existing data, don't fetch new data
- "search for weather" → Use search tool  
- "what did we discuss?" → Offer to search or show history
- "how many messages?" → Use database tool

Be intelligent, context-aware, and user-focused."""

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


@mcp.tool()
async def chat_with_llm(message: str, session_id: str = None, include_history: bool = True) -> str:
    """
    Chat with the LLM with enhanced tool usage and anti-hallucination measures.
    
    Args:
        message: Message to send to the LLM
        session_id: Session ID for conversation context (optional)
        include_history: Whether to include conversation history (default: True)
    """
    return await _chat_with_llm_impl(message, session_id, include_history)


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
    logger.add("logs/mcp_server_refined.log", rotation="1 day", retention="7 days")
    logger.info("Starting APE MCP Server - Refined Version")
    
    # The FastMCP server will be automatically run by the mcp dev command
    print("APE MCP Server (Refined) is ready!") 