from llama_index.llms.ollama import Ollama
from loguru import logger
from ape import config
from ape.utils import setup_logger
import httpx
import json

# Multimodal import
try:
    from llama_index.multi_modal_llms.ollama import OllamaMultiModal
    from llama_index.core.schema import ImageDocument
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False
    logger.warning("llama-index-multi-modal-llms-ollama not installed. Multimodal support disabled.")

setup_logger()

_llm = None
_mm_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = Ollama(
            model=config.LLM_MODEL,
            base_url=f"http://{config.OLLAMA_HOST}",
            request_timeout=120.0,
            context_window=8000,
        )
        logger.info(f"Loaded LLM model: {config.LLM_MODEL} at {config.OLLAMA_HOST}")
    return _llm

def get_multimodal_llm():
    global _mm_llm
    if not MULTIMODAL_AVAILABLE:
        return None
    if _mm_llm is None:
        _mm_llm = OllamaMultiModal(
            model=config.MULTIMODAL_MODEL,
            base_url=f"http://{config.OLLAMA_HOST}"
        )
        logger.info(f"Loaded multimodal model: {config.MULTIMODAL_MODEL} at {config.OLLAMA_HOST}")
    return _mm_llm

def llm_complete(text, image_documents=None):
    if image_documents and MULTIMODAL_AVAILABLE:
        mm_llm = get_multimodal_llm()
        return mm_llm.complete(prompt=text, image_documents=image_documents)
    else:
        llm = get_llm()
        return llm.complete(text)

def llm_stream_complete(text: str | None = None, image_base64: str | None = None):
    """
    Streams a response from the Ollama chat API, bypassing LlamaIndex.
    """
    logger.info("[LLM_STREAM] Starting direct stream to Ollama.")

    model = config.LLM_MODEL
    messages = [{"role": "user", "content": text or "Describe the image"}]
    
    if image_base64:
        model = config.MULTIMODAL_MODEL if MULTIMODAL_AVAILABLE else config.LLM_MODEL
        messages[0]["images"] = [image_base64]
        logger.info(f"[LLM_STREAM] Using model {model} for multimodal request.")
    else:
        logger.info(f"[LLM_STREAM] Using model {model} for text request.")

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    try:
        with httpx.stream(
            "POST",
            f"http://{config.OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=None,
        ) as response:
            response.raise_for_status()
            logger.info("[LLM_STREAM] Connection to Ollama successful. Streaming response...")
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if not chunk.get("done"):
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                    else:
                        logger.info("[LLM_STREAM] Stream finished.")
                        break
                except json.JSONDecodeError:
                    logger.warning(f"[LLM_STREAM] Failed to decode JSON line: {line}")
                    continue
    except httpx.RequestError as e:
        logger.error(f"[LLM_STREAM] HTTP request error to Ollama: {e}")
        yield f"[ERROR] Could not connect to Ollama: {e}\\n"
    except Exception as e:
        logger.error(f"[LLM_STREAM] An unexpected error occurred: {e}", exc_info=True)
        yield f"[ERROR] An unexpected error occurred during streaming: {e}\\n" 