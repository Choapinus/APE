from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from ape.schemas import PromptRequest, PromptResponse
from ape.session import SessionManager
from ape.llm import llm_complete, llm_stream_complete
from ape.utils import decode_base64_image
from loguru import logger
from typing import List
import asyncio
import inspect
import logging
import httpx
import json
from ape import config

try:
    from llama_index.core.schema import ImageDocument
except ImportError:
    ImageDocument = None

router = APIRouter()
session_manager = SessionManager()

@router.post("/prompt", response_model=PromptResponse)
def prompt_endpoint(request: PromptRequest):
    session_id = request.session_id or str(session_manager.__hash__())
    session_manager.create_session(session_id)
    logger.info(f"Received /prompt request: session_id={session_id}, text_present={bool(request.text)}, image_present={bool(request.image_base64)}")
    try:
        image_documents = None
        if request.image_base64 and ImageDocument is not None:
            try:
                image = decode_base64_image(request.image_base64)
                image_doc = ImageDocument(pil_image=image)
                image_documents = [image_doc]
            except Exception as e:
                logger.error(f"Error decoding image: {e}")
                return PromptResponse(text="Error processing image input.", session_id=session_id)
        if request.text or image_documents:
            response = llm_complete(request.text or "Describe the image.", image_documents=image_documents)
            session_manager.append_turn(session_id, request.text or "[image]", response, image=bool(image_documents))
            return PromptResponse(text=str(response), session_id=session_id)
        else:
            logger.warning(f"No text or image input provided in /prompt for session_id={session_id}")
            return PromptResponse(text="Please provide text and/or image input.", session_id=session_id)
    except Exception as e:
        logger.error(f"Error in /prompt endpoint: {e}")
        return PromptResponse(text="An error occurred while processing your request.", session_id=session_id)

@router.post("/prompt/stream")
def prompt_stream_endpoint(request: PromptRequest):
    session_id = request.session_id or str(session_manager.__hash__())
    session_manager.create_session(session_id)
    logger.info(f"Received /prompt/stream request: session_id={session_id}, text_present={bool(request.text)}, image_present={bool(request.image_base64)}")

    return StreamingResponse(
        llm_stream_complete(text=request.text, image_base64=request.image_base64),
        media_type="text/plain"
    )

@router.get("/session")
def get_sessions():
    return session_manager.get_all_sessions() 