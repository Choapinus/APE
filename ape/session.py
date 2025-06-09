from loguru import logger

class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_session(self, session_id):
        return self.sessions.get(session_id, [])

    def create_session(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            logger.info(f"Created new session: {session_id}")

    def append_turn(self, session_id, user, llm, image=False):
        if session_id not in self.sessions:
            self.create_session(session_id)
        self.sessions[session_id].append({
            "user": user,
            "llm": llm,
            "image": image
        })
        logger.info(f"Session {session_id} history length: {len(self.sessions[session_id])}")

    def get_history(self, session_id):
        return self.sessions.get(session_id, []) 