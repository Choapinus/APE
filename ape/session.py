import sqlite3
import json
from loguru import logger

class SessionManager:
    def __init__(self, db_path="ape/sessions.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _create_table(self):
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        images TEXT, -- JSON serialized list of base64 strings
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Database table 'history' is ready.")
        except sqlite3.Error as e:
            logger.error(f"Database error on table creation: {e}")
            raise

    def save_messages(self, session_id: str, messages: list):
        """Saves a complete list of messages for a session, overwriting the existing history."""
        try:
            with self.conn:
                # Clear the old history for this session
                self.conn.execute("DELETE FROM history WHERE session_id = ?", (session_id,))
                
                # Insert all new messages
                for message in messages:
                    self.conn.execute(
                        "INSERT INTO history (session_id, role, content, images) VALUES (?, ?, ?, ?)",
                        (
                            session_id,
                            message.get("role"),
                            message.get("content"),
                            json.dumps(message.get("images")) if message.get("images") else None,
                        ),
                    )
            logger.info(f"Saved {len(messages)} messages to session {session_id}.")
        except sqlite3.Error as e:
            logger.error(f"Failed to save messages for session {session_id}: {e}")

    def get_session(self, session_id):
        return self.get_history(session_id)

    def create_session(self, session_id):
        # With DB backend, session is created on first turn.
        # This can be used to check for existence if needed, but for now it's a no-op.
        logger.debug(f"Session check/creation for ID: {session_id}")

    def get_history(self, session_id):
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "SELECT role, content, images FROM history WHERE session_id = ? ORDER BY timestamp ASC",
                    (session_id,),
                )
                history = []
                for row in cursor.fetchall():
                    role, content, images_json = row
                    message = {"role": role, "content": content}
                    if images_json:
                        message["images"] = json.loads(images_json)
                    history.append(message)
                return history
        except sqlite3.Error as e:
            logger.error(f"Failed to get history for session {session_id}: {e}")
            return []

    def get_all_sessions(self) -> dict:
        try:
            with self.conn:
                cursor = self.conn.execute("SELECT DISTINCT session_id FROM history")
                session_ids = [row[0] for row in cursor.fetchall()]
                sessions = {}
                for session_id in session_ids:
                    sessions[session_id] = self.get_history(session_id)
                return sessions
        except sqlite3.Error as e:
            logger.error(f"Failed to get all sessions: {e}")
            return {}

_session_manager: SessionManager | None = None

def get_session_manager():
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager 