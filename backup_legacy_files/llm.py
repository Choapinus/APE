import os
import json
import asyncio
from typing import List, Dict, Any, Optional, Union, Type
from pydantic import BaseModel, ValidationError
import instructor
from ollama import Client
from openai import OpenAI
from loguru import logger
from ape import config
from ape.utils import setup_logger
import time
from ape.tools import AVAILABLE_TOOLS, TOOL_DEFINITIONS, BaseTool
from pydantic import BaseModel, Field
from typing import Union, List, Optional, Literal
import re
from datetime import datetime

# Ollama client for direct API calls
ollama_client = Client(host='http://localhost:11434')

# Instructor client for structured outputs with Ollama
client = instructor.from_openai(
    OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # required, but unused
    ),
    mode=instructor.Mode.JSON,
)

setup_logger()

class ReActResponse(BaseModel):
    """
    Structured response following the ReAct (Reasoning and Acting) pattern.
    This ensures the LLM follows the proper Thought -> Action -> Observation flow.
    """
    thought: str = Field(
        default="I need to process this request.",
        description="Your reasoning about what the user needs and what you should do"
    )
    action: Optional[str] = Field(
        default=None,
        description="Name of the tool to use, or None if no tool is needed"
    )
    action_input: Optional[dict] = Field(
        default=None,
        description="Arguments for the tool as a JSON object, or None if no tool is used"
    )
    final_answer: Optional[str] = Field(
        default=None,
        description="Your complete response to the user when you have all needed information"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "thought": "The user is greeting me, no tool is needed.",
                    "action": None,
                    "action_input": None,
                    "final_answer": "Hello! How can I help you today?"
                },
                {
                    "thought": "The user wants to see interactions, I need to use GetLastNInteractionsTool.",
                    "action": "GetLastNInteractionsTool",
                    "action_input": {"n": 5},
                    "final_answer": None
                },
                {
                    "thought": "The user wants database information, I should use DatabaseInfoTool.",
                    "action": "DatabaseInfoTool",
                    "action_input": {},
                    "final_answer": None
                },
                {
                    "thought": "The user wants a database query, I should use GenerateDatabaseQueryTool.",
                    "action": "GenerateDatabaseQueryTool",
                    "action_input": {"query_description": "recent messages", "limit": 10},
                    "final_answer": None
                }
            ]
        }

class MCPOrchestrator:
    """
    MCP-compliant orchestrator that manages tool calling and result handling
    using Pydantic-validated structured responses for reliability.
    """
    
    def __init__(self, session_manager, session_id: str):
        self.session_manager = session_manager
        self.session_id = session_id
        self.max_iterations = 5
        
    def get_system_prompt(self) -> str:
        """Builds system prompt for structured ReAct agent with MCP tool definitions"""
        tools_json = json.dumps(TOOL_DEFINITIONS, indent=2)
        return (
            "You are a helpful AI assistant that follows the ReAct pattern (Reasoning and Acting).\n\n"
            "For each user request, think step by step and use tools when needed.\n\n"
            "Available tools (MCP-compliant):\n"
            f"{tools_json}\n\n"
            "You MUST ALWAYS respond with a valid JSON object containing these exact fields:\n"
            "{\n"
            '  "thought": "Your reasoning about what to do",\n'
            '  "action": "ToolName or null",\n'
            '  "action_input": {"arg": "value"} or null,\n'
            '  "final_answer": "Your response" or null\n'
            "}\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "- ALWAYS include the 'thought' field - never omit it\n"
            "- If you need a tool: set 'action' to tool name, set 'action_input' to {} (empty object) for tools without args, set 'final_answer' to null\n"
            "- If no tool needed: set 'action' and 'action_input' to null, provide 'final_answer'\n"
            "- When you receive tool results, provide a 'final_answer' based on those results\n"
            "- Never make up tool results - only use real tool outputs\n"
            "- For database questions: use DatabaseInfoTool first, then GenerateDatabaseQueryTool if needed\n"
            "- For interaction history: use GetLastNInteractionsTool\n"
            "- Always try to help users with available tools before saying you can't help"
        )
    
    def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool using MCP pattern and return observation"""
        logger.info(f"[MCP Orchestrator] Executing tool: {tool_name} with args: {tool_args}")
        
        tool = AVAILABLE_TOOLS.get(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found. Available tools: {list(AVAILABLE_TOOLS.keys())}"
        
        try:
            # Handle tools with no arguments gracefully
            if not tool_args and hasattr(tool.Args, 'model_fields') and not tool.Args.model_fields:
                # Tool has no arguments, call directly
                result = tool.execute()
            else:
                # Tool has arguments, validate and pass them
                validated_args = tool.Args.model_validate(tool_args)
                result = tool.execute(**validated_args.model_dump())
            
            logger.info(f"[MCP Orchestrator] Tool executed successfully")
            return result  # Return just the result, not the wrapper message
        except ValidationError as e:
            error_msg = f"Invalid arguments for tool '{tool_name}': {e}"
            logger.error(f"[MCP Orchestrator] {error_msg}")
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {e}"
            logger.error(f"[MCP Orchestrator] {error_msg}")
            return f"Error: {error_msg}"
    
    def run_react_loop(self, initial_messages: list) -> str:
        """
        Main ReAct loop with proper MCP orchestration using structured responses
        """
        messages = list(initial_messages)
        
        for iteration in range(self.max_iterations):
            logger.debug(f"[MCP Orchestrator] ReAct iteration {iteration + 1}/{self.max_iterations}")
            
            try:
                # Get structured response from the LLM using instructor
                response: ReActResponse = client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=messages,
                    response_model=ReActResponse,
                    max_retries=2,
                    temperature=0.1  # Lower temperature for more consistent structured output
                )
                
                # Validate the response has at least thought and final_answer or action
                if not response.thought:
                    response.thought = "I need to process this request."
                if not response.final_answer and not response.action:
                    response.final_answer = "I understand your request, but I need more specific information to help you."
                
                logger.debug(f"[MCP Orchestrator] Structured response - Thought: {response.thought}")
                logger.debug(f"[MCP Orchestrator] Structured response - Action: {response.action}")
                logger.debug(f"[MCP Orchestrator] Structured response - Final Answer: {response.final_answer}")
                
                # If there's a final answer, we're done
                if response.final_answer:
                    logger.info(f"[MCP Orchestrator] Final answer provided, completing")
                    messages.append({"role": "assistant", "content": response.final_answer})
                    self.session_manager.save_messages(self.session_id, messages[1:])
                    return response.final_answer
                
                # If there's an action to execute
                if response.action:
                    logger.info(f"[MCP Orchestrator] Executing action: {response.action}")
                    
                    # Handle tools that don't need arguments
                    tool_args = response.action_input if response.action_input is not None else {}
                    
                    # Execute the tool
                    observation = self.execute_tool(response.action, tool_args)
                    
                    # Build the complete response with observation for conversation history
                    complete_response = f"Thought: {response.thought}\n"
                    complete_response += f"Action: {response.action}\n"
                    complete_response += f"Action Input: {json.dumps(response.action_input)}\n"
                    complete_response += f"Observation: {observation}\n"
                    
                    # Add the complete response to messages
                    messages.append({"role": "assistant", "content": complete_response})
                    
                    # Add a user message asking for final answer with the observation included
                    messages.append({
                        "role": "user", 
                        "content": f"Based on the tool observation: {observation}\n\nPlease provide your final answer to my original question. Do not execute any more tools."
                    })
                    
                    # Continue the loop to get final answer
                    continue
                
                # If no action but we have a thought, treat it as a direct response
                if not response.action and response.thought:
                    logger.info(f"[MCP Orchestrator] No action needed, providing direct response")
                    final_response = response.final_answer or "I understand your request, but I need more specific information to help you."
                    messages.append({"role": "assistant", "content": final_response})
                    self.session_manager.save_messages(self.session_id, messages[1:])
                    return final_response
                
                # This shouldn't happen with proper Pydantic validation
                logger.warning(f"[MCP Orchestrator] Unexpected response structure: action={response.action}, final_answer={response.final_answer}")
                # Try to recover by providing a helpful response
                if response.thought and "database" in response.thought.lower():
                    return "I can help you with database information. Let me try using my DatabaseInfoTool."
                return "I understand your request but need clarification. Could you please be more specific?"
                
            except ValidationError as e:
                logger.error(f"[MCP Orchestrator] Validation error in iteration {iteration}: {e}")
                logger.error(f"[MCP Orchestrator] Messages that caused error: {messages[-3:]}")
                
                # Try to create a manual fallback response for common cases
                user_message = messages[-1].get("content", "").lower() if messages else ""
                
                if any(word in user_message for word in ["tool", "database", "info", "schema"]):
                    # User is asking about tools or database - try DatabaseInfoTool
                    try:
                        from ape.tools import DatabaseInfoTool
                        db_tool = DatabaseInfoTool()
                        result = db_tool.execute()
                        final_response = f"Here's information about the database:\n\n{result}"
                        messages.append({"role": "assistant", "content": final_response})
                        self.session_manager.save_messages(self.session_id, messages[1:])
                        return final_response
                    except Exception:
                        pass
                
                # General fallback
                if iteration == 0:
                    return "I understand your request but had trouble processing it. Could you please rephrase your question?"
                else:
                    return "I encountered a validation error while processing your request."
            except Exception as e:
                logger.error(f"[MCP Orchestrator] Error in iteration {iteration}: {e}")
                return f"I encountered an error: {e}"
        
        logger.warning(f"[MCP Orchestrator] Reached maximum iterations without completion")
        return "I'm sorry, I couldn't complete your request after multiple attempts."

def _run_agent_loop(initial_messages: list, session_manager, session_id: str) -> str:
    """
    Main entry point that creates and runs the MCP orchestrator
    """
    orchestrator = MCPOrchestrator(session_manager, session_id)
    return orchestrator.run_react_loop(initial_messages)

def llm_complete(text: str | None = None, image_base64: str | None = None, session_id: str | None = None, session_manager=None):
    """
    Orchestrates a non-streaming completion using MCP ReAct pattern with structured responses.
    """
    logger.debug("[LLM_COMPLETE] Orchestrating non-streaming request")
    history = session_manager.get_history(session_id)
    new_turn = {"role": "user", "content": text or ""}
    if image_base64:
        new_turn["images"] = [image_base64]
    
    orchestrator = MCPOrchestrator(session_manager, session_id)
    system_prompt = {"role": "system", "content": orchestrator.get_system_prompt()}
    initial_messages = [system_prompt] + history + [new_turn]
    
    return _run_agent_loop(initial_messages, session_manager, session_id)

def llm_stream_complete(text: str | None = None, image_base64: str | None = None, session_id: str | None = None, session_manager=None):
    """
    Orchestrates a streaming completion using MCP ReAct pattern with structured responses.
    """
    logger.debug(f"[LLM_STREAM] Orchestrating request for session: {session_id}")
    history = session_manager.get_history(session_id)
    new_turn = {"role": "user", "content": text}
    if image_base64:
        new_turn["images"] = [image_base64]

    orchestrator = MCPOrchestrator(session_manager, session_id)
    system_prompt = {"role": "system", "content": orchestrator.get_system_prompt()}
    initial_messages = [system_prompt] + history + [new_turn]

    final_content = _run_agent_loop(initial_messages, session_manager, session_id)

    # Stream the final content with typewriter effect
    for char in final_content:
        yield char
        time.sleep(0.01) 