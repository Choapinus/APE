"""Session management for APE MCP Server."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from loguru import logger
from ape.settings import settings
from ape.db_pool import get_db

# Configuration
DB_PATH = settings.SESSION_DB_PATH


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
        
        # New: table for structured tool error logging
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                arguments TEXT,
                error TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        
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
    
    async def a_get_all_sessions(self) -> List[Dict[str, Any]]:
        """Async version of get_all_sessions using aiosqlite."""
        try:
            from ape.db_pool import get_db

            async with get_db() as conn:
                query_ids = (
                    "SELECT session_id, COUNT(*) as message_count, "
                    "MIN(timestamp) as first_ts, MAX(timestamp) as last_ts "
                    "FROM history GROUP BY session_id ORDER BY MAX(timestamp) DESC"
                )
                async with conn.execute(query_ids) as cursor:
                    rows = await cursor.fetchall()

            sessions: List[Dict[str, Any]] = []
            for session_id, count, first_ts, last_ts in rows:
                first_message = ""  # placeholders – expensive joins removed for perf
                last_message = ""
                sessions.append(
                    {
                        "session_id": session_id,
                        "message_count": count,
                        "first_message": first_message,
                        "last_message": last_message,
                    }
                )
            return sessions
        except Exception as exc:
            logger.error(f"[async] Error getting sessions: {exc}")
            return []

    async def a_save_error(self, tool: str, arguments: dict | None, error: str):
        """Async version of save_error."""
        try:
            from ape.db_pool import get_db

            async with get_db() as conn:
                await conn.execute(
                    "INSERT INTO tool_errors (tool, arguments, error) VALUES (?, ?, ?)",
                    (
                        tool,
                        json.dumps(arguments or {}),
                        error,
                    ),
                )
                await conn.commit()
        except Exception as exc:
            logger.error(f"[async] Error saving tool error: {exc}")

    # -------------------- Sync wrappers (deprecated) --------------------

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Deprecated sync wrapper delegating to ``a_get_all_sessions``."""
        import asyncio

        try:
            return asyncio.run(self.a_get_all_sessions())
        except RuntimeError:
            # Already inside an event loop → fallback to blocking call with nested loop
            loop = asyncio.get_event_loop()
            fut = asyncio.ensure_future(self.a_get_all_sessions(), loop=loop)
            return loop.run_until_complete(fut)

    def save_error(self, tool: str, arguments: dict | None, error: str):
        """Deprecated sync wrapper delegating to ``a_save_error``."""
        import asyncio

        try:
            asyncio.run(self.a_save_error(tool, arguments, error))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            fut = asyncio.ensure_future(self.a_save_error(tool, arguments, error), loop=loop)
            loop.run_until_complete(fut)

    # ------------------------------------------------------------------
    # Async variants (Step 1 – aiosqlite migration)
    # ------------------------------------------------------------------

    async def a_save_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        """Async version of save_messages using aiosqlite.

        This is part of the planned migration to fully-async DB access while
        retaining backwards-compatible synchronous wrappers.  Callers that are
        already inside an event loop should prefer this coroutine.
        """
        try:
            from ape.db_pool import get_db

            async with get_db() as conn:
                await conn.execute("DELETE FROM history WHERE session_id = ?", (session_id,))

                insert_sql = (
                    "INSERT INTO history (session_id, role, content, images, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)"
                )
                for msg in messages:
                    await conn.execute(
                        insert_sql,
                        (
                            session_id,
                            msg.get("role"),
                            msg.get("content"),
                            json.dumps(msg.get("images", [])),
                            msg.get("timestamp", datetime.now().isoformat()),
                        ),
                    )
                await conn.commit()
        except Exception as exc:
            logger.error(f"[async] Error saving messages: {exc}")
            raise

    async def a_get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Async version of get_history using aiosqlite."""
        try:
            from ape.db_pool import get_db

            async with get_db() as conn:
                query = (
                    "SELECT role, content, images, timestamp "
                    "FROM history WHERE session_id = ? ORDER BY timestamp ASC"
                )
                async with conn.execute(query, (session_id,)) as cursor:
                    rows = await cursor.fetchall()

            messages: List[Dict[str, Any]] = []
            for role, content, images, timestamp in rows:
                msg: Dict[str, Any] = {
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                }
                if images:
                    msg["images"] = json.loads(images)
                messages.append(msg)
            return messages
        except Exception as exc:
            logger.error(f"[async] Error getting history: {exc}")
            return []


# Global session manager instance
_session_manager = None


def get_session_manager() -> SessionManager:
    """Get or create the global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager 