"""Implementation functions for APE MCP tools."""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional

from loguru import logger

# Configuration
DB_PATH = "ape/sessions.db"


async def execute_database_query_impl(sql_query: str) -> str:
    """Implementation of execute_database_query without MCP decoration."""
    try:
        # Security: Only allow SELECT statements
        if not sql_query.strip().upper().startswith('SELECT'):
            return "Error: Only SELECT queries are allowed for security reasons."
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(sql_query)
        
        # Get column names
        columns = [description[0] for description in cursor.description]
        
        # Fetch results
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "Query executed successfully, but no results found."
        
        # Format as JSON
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            results.append(row_dict)
        
        return json.dumps(results, indent=2, default=str)
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return f"Database error: {str(e)}"
    except Exception as e:
        logger.error(f"Error executing database query: {e}")
        return f"Error executing database query: {str(e)}"


async def get_conversation_history_impl(session_id: str = None, limit: int = 10) -> str:
    """Implementation of get_conversation_history without MCP decoration."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if session_id:
            # Get history for specific session
            sql_query = """
                SELECT role, content, timestamp 
                FROM history 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(sql_query, (session_id, limit))
        else:
            # Get recent history across all sessions
            sql_query = """
                SELECT role, content, timestamp 
                FROM history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            cursor.execute(sql_query, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "No conversation history found."
        
        # Format the history
        history = []
        for role, content, timestamp in reversed(rows):  # Reverse to show chronological order
            history.append({
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        
        return json.dumps(history, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return f"Error getting conversation history: {str(e)}"


async def get_database_info_impl() -> str:
    """Implementation of get_database_info without MCP decoration."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(history)")
        schema_info = cursor.fetchall()
        
        schema = {}
        for row in schema_info:
            column_id, name, data_type, not_null, default_value, primary_key = row
            schema[name] = {
                "type": data_type,
                "not_null": bool(not_null),
                "default": default_value,
                "primary_key": bool(primary_key)
            }
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM history")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM history")
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT role, COUNT(*) 
            FROM history 
            GROUP BY role
        """)
        role_counts = dict(cursor.fetchall())
        
        # Get recent activity (last 7 days)
        cursor.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM history 
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """)
        recent_activity = dict(cursor.fetchall())
        
        conn.close()
        
        info = {
            "database_path": DB_PATH,
            "schema": schema,
            "statistics": {
                "total_messages": total_messages,
                "total_sessions": total_sessions,
                "messages_by_role": role_counts,
                "recent_activity_7_days": recent_activity
            }
        }
        
        return json.dumps(info, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return f"Error getting database info: {str(e)}"


async def search_conversations_impl(query: str, limit: int = 5) -> str:
    """Implementation of search_conversations without MCP decoration."""
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
        
        # Format results
        results = []
        for session_id, role, content, timestamp in rows:
            # Truncate long content
            display_content = content[:200] + "..." if len(content) > 200 else content
            
            results.append({
                "session_id": session_id,
                "role": role,
                "content": display_content,
                "timestamp": timestamp,
                "relevance": "Contains: " + query
            })
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        return f"Error searching conversations: {str(e)}" 