import os

# General settings
PORT = int(os.environ.get("PORT", 8000))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", OLLAMA_HOST)
TEMPERATURE = float(os.environ.get("TEMPERATURE", 0.2)) # 0.2 for "more" creative problem solving
MAX_TOOLS_ITERATIONS = int(os.environ.get("MAX_TOOLS_ITERATIONS", 15)) # 15 for complex tasks

# LLM settings
# LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.1") # tools capable, but its too rigid
# LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:4b") # no tools usage
# LLM_MODEL = os.environ.get("LLM_MODEL", "orieg/gemma3-tools:4b-it-qat") # fair enough, with overuse of tools
# LLM_MODEL = os.environ.get("LLM_MODEL", "orieg/gemma3-tools:1b-it-qat") # not good enough but fair. It doesnt recognize at all its tools
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b") # good
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:14b") # pretty cool
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:30b-a3b") # I think this is the best 
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:30b-a3b-q4_K_M") # 
# 
# LLM_MODEL = "PetrosStav/gemma3-tools:12b"

# UI settings
UI_THEME = os.environ.get("UI_THEME", "dark")
SHOW_THOUGHTS = os.environ.get("SHOW_THOUGHTS", "true").lower() == "true" 