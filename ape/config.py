import os

# General settings
PORT = int(os.environ.get("PORT", 8000))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", OLLAMA_HOST)

# LLM settings
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:4b")

# UI settings
UI_THEME = os.environ.get("UI_THEME", "dark")
SHOW_THOUGHTS = os.environ.get("SHOW_THOUGHTS", "true").lower() == "true" 