from ape.settings import settings as _s

# Backwards-compatibility shim.  Prefer importing `from ape.settings import settings` going forward.
PORT = _s.PORT
LOG_LEVEL = _s.LOG_LEVEL
OLLAMA_BASE_URL = _s.OLLAMA_BASE_URL
TEMPERATURE = _s.TEMPERATURE
MAX_TOOLS_ITERATIONS = _s.MAX_TOOLS_ITERATIONS
LLM_MODEL = _s.LLM_MODEL
UI_THEME = _s.UI_THEME
SHOW_THOUGHTS = _s.SHOW_THOUGHTS

# General settings
# LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.1") # tools capable, but its too rigid
# LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:4b") # no tools usage
# LLM_MODEL = os.environ.get("LLM_MODEL", "orieg/gemma3-tools:4b-it-qat") # fair enough, with overuse of tools
# LLM_MODEL = os.environ.get("LLM_MODEL", "orieg/gemma3-tools:1b-it-qat") # not good enough but fair. It doesnt recognize at all its tools
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b") # good
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:14b") # pretty cool
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:30b-a3b") # I think this is the best 
# LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:30b-a3b-q4_K_M") # 
# 
# LLM_MODEL = "PetrosStav/gemma3-tools:12b"

# UI settings
# UI_THEME = os.environ.get("UI_THEME", "dark")
# SHOW_THOUGHTS = os.environ.get("SHOW_THOUGHTS", "true").lower() == "true" 