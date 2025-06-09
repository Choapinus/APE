from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from ape.schemas import PromptRequest, PromptResponse
from ape.session import SessionManager, get_session_manager
from ape.llm import llm_complete, llm_stream_complete
from loguru import logger
from typing import List
import asyncio
import inspect
import logging
import httpx
import json
from ape import config
from ape.tools import TOOL_DEFINITIONS

router = APIRouter()

@router.post("/prompt", response_model=PromptResponse)
def prompt_endpoint(request: PromptRequest, session_manager: SessionManager = Depends(get_session_manager)):
    session_id = request.session_id or str(session_manager.__hash__())
    session_manager.create_session(session_id)
    logger.info(f"Received /prompt request: session_id={session_id}, text_present={bool(request.text)}, image_present={bool(request.image_base64)}")
    try:
        if request.text or request.image_base64:
            response_text = llm_complete(
                text=(request.text or "Describe the image."),
                image_base64=request.image_base64,
                session_id=session_id,
                session_manager=session_manager
            )
            return PromptResponse(text=response_text, session_id=session_id)
        else:
            logger.warning(f"No text or image input provided in /prompt for session_id={session_id}")
            return PromptResponse(text="Please provide text and/or image input.", session_id=session_id)
    except Exception as e:
        logger.error(f"Error in /prompt endpoint: {e}")
        return PromptResponse(text="An error occurred while processing your request.", session_id=session_id)

@router.post("/prompt/stream")
def prompt_stream_endpoint(request: PromptRequest, session_manager: SessionManager = Depends(get_session_manager)):
    session_id = request.session_id or str(session_manager.__hash__())
    session_manager.create_session(session_id)
    logger.info(f"Received /prompt/stream request: session_id={session_id}, text_present={bool(request.text)}, image_present={bool(request.image_base64)}")

    return StreamingResponse(
        llm_stream_complete(
            text=request.text,
            image_base64=request.image_base64,
            session_id=session_id,
            session_manager=session_manager
        ),
        media_type="text/plain"
    )

@router.get("/session")
def get_sessions(session_manager: SessionManager = Depends(get_session_manager)):
    return session_manager.get_all_sessions()

@router.get("/tools/list")
def list_tools():
    """
    Exposes the available tools to the agent, following an MCP-like discovery pattern.
    """
    return {"tools": TOOL_DEFINITIONS} 