from fastapi import FastAPI
from ape.api import router as ape_router
from loguru import logger
from ape.llm import llm_complete
from ape.session import get_session_manager
from ape import config
import uuid

app = FastAPI()
app.include_router(ape_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Pinging LLM at startup to ensure the model is loaded...")
    try:
        # We need a session manager instance for the check
        session_manager = get_session_manager()
        # Use a unique session ID to avoid accumulated history
        unique_session_id = f"startup-check-{uuid.uuid4().hex[:8]}"
        response = llm_complete(
            text="Hello, are you working?",
            session_id=unique_session_id,
            session_manager=session_manager
        )
        if "ERROR" in response:
            raise RuntimeError(response)
        logger.info("Ollama connection successful. Main LLM model should be available.")
    except Exception as e:
        logger.error(f"Failed to connect to Ollama on startup: {e}")

@app.get("/health")
def health_check():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
