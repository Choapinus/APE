import os

LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:4b")
MULTIMODAL_MODEL = os.environ.get("MULTIMODAL_MODEL", "llava:13b")
PORT = int(os.environ.get("PORT", 8000))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost") 