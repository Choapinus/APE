"""Session management for APE MCP Server."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger

# Configuration
DB_PATH = "ape/sessions.db"


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
            
            # Get basic session info
            cursor.execute("""
                SELECT session_id, COUNT(*) as message_count
                FROM history
                GROUP BY session_id
                ORDER BY MAX(timestamp) DESC
            """)
            
            session_rows = cursor.fetchall()
            
            sessions = []
            for session_id, count in session_rows:
                # Get first message content (oldest record by ID)
                cursor.execute("""
                    SELECT content FROM history 
                    WHERE session_id = ? 
                    ORDER BY id ASC 
                    LIMIT 1
                """, (session_id,))
                first_result = cursor.fetchone()
                first_message = first_result[0][:100]+"..." if first_result else ""
                
                # Get last message content (newest record by ID)
                cursor.execute("""
                    SELECT content FROM history 
                    WHERE session_id = ? 
                    ORDER BY id DESC 
                    LIMIT 1
                """, (session_id,))
                last_result = cursor.fetchone()
                last_message = last_result[0][:100]+"..." if last_result else ""
                
                sessions.append({
                    "session_id": session_id,
                    "message_count": count,
                    "first_message": first_message,
                    "last_message": last_message
                })
            
            conn.close()
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return []


# Global session manager instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager 