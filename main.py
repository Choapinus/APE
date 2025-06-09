from fastapi import FastAPI
from ape.api import router as ape_router
from loguru import logger
from ape.llm import get_llm, get_multimodal_llm, MULTIMODAL_AVAILABLE
from ape import config

app = FastAPI()
app.include_router(ape_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Pinging LLM(s) at startup to ensure models are loaded...")
    try:
        llm = get_llm()
        # Try a trivial completion to force model load
        llm.complete("ping")
        logger.info("Main LLM model loaded and responsive.")
    except Exception as e:
        logger.error(f"Failed to load main LLM model: {e}")
    # Only ping multimodal LLM if main model is not gemma3:4b
    if MULTIMODAL_AVAILABLE and config.LLM_MODEL != "gemma3:4b":
        try:
            mm_llm = get_multimodal_llm()
            mm_llm.complete(prompt="ping", image_documents=[])
            logger.info("Multimodal LLM model loaded and responsive.")
        except Exception as e:
            logger.error(f"Failed to load multimodal LLM model: {e}")

@app.get("/health")
def health_check():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
