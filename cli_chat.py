#!/usr/bin/env python3
"""
APE CLI Chat Interface

A command-line interface that uses the official MCP Python SDK to connect to the APE MCP server.
This demonstrates proper MCP client/server communication.
"""

import asyncio
import sys
import uuid
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from loguru import logger
import ollama
from ape.utils import setup_logger

from ape.mcp.session_manager import get_session_manager
from ape.cli.context_manager import ContextManager
from ape.cli.mcp_client import MCPClient
from ape.cli.chat_agent import ChatAgent
from ape.settings import settings

# Better CLI input handling (arrow keys, history)
try:
    from prompt_toolkit import PromptSession
except ImportError:  # fallback if library not installed
    PromptSession = None

class APEChatCLI:
    """Command-line interface for APE chat functionality using MCP."""
    
    def __init__(self):
        # ------------------------------------------------------------------
        # Bootstrapping: configure log sinks once per process
        # ------------------------------------------------------------------
        setup_logger()

        self.session_id = str(uuid.uuid4())
        self.session_manager = get_session_manager()
        # Wrapper that manages the underlying MCP stdio connection
        self.mcp_client = MCPClient()
        # Kept for backward compatibility; will be removed in follow-up refactor
        self.mcp_session = None
        self.context_manager = ContextManager(self.session_id)
        self.chat_agent = ChatAgent(self.session_id, self.mcp_client, self.context_manager)
        logger.info(f"Started new chat session: {self.session_id}")
        
        # Initialise prompt session for nicer input UX if available
        self.prompt: Optional[PromptSession] = None
        if PromptSession is not None:
            self.prompt = PromptSession()
    
    def print_banner(self):
        """Print the APE CLI banner."""
        print("\n" + "="*60)
        print("🤖 APE (Agentic Protocol Executor) - CLI Chat")
        print("="*60)
        print("Session ID:", self.session_id[:8] + "...")
        print("\nCommands:")
        print("  /help     - Show this help")
        print("  /history  - Show conversation history")
        print("  /session  - Show session info")
        print("  /tools    - List available MCP tools")
        print("  /context  - Show current session context")
        print("  /clear    - Clear screen")
        print("  /reset    - Clear session context")
        print("  /quit     - Exit chat")
        print("  /exit     - Exit chat")
        print("  /q        - Exit chat")
        print("\n🧠 Intelligence: Connected to MCP server with tools:")
        print("  • Database tools for conversation management")
        print("  • Search tools for finding content")
        print("  • History tools for context retrieval")
        print("="*60 + "\n")
    
    async def connect_to_mcp(self):
        """Connect to the MCP server through the reusable wrapper."""
        success = await self.mcp_client.connect()
        if success:
            # expose underlying session for legacy code paths (to be removed later)
            self.mcp_session = self.mcp_client.mcp_session
        return success
    
    async def disconnect_from_mcp(self):
        """Disconnect via the reusable wrapper."""
        await self.mcp_client.disconnect()
        self.mcp_session = None
    
    async def list_tools(self):
        """List available MCP tools."""
        try:
            if not self.mcp_client.is_connected:
                print("❌ Not connected to MCP server")
                return
            
            logger.info("🔧 [MCP CLIENT] Requesting tool list from MCP server")
            tools_result = await self.mcp_client.list_tools()
            logger.info(f"✅ [MCP CLIENT] Received {len(tools_result.tools)} tools from server")
            
            print(f"\n🔧 Available MCP Tools ({len(tools_result.tools)}):")
            print("-" * 50)
            
            for tool in tools_result.tools:
                print(f"• {tool.name}: {tool.description}")
                
            print("-" * 50)
            
        except Exception as e:
            logger.error(f"❌ [MCP CLIENT] Error listing tools: {e}")
            print(f"❌ Error listing tools: {e}")
    
    async def show_history(self, limit: int = 10):
        """Show conversation history using MCP."""
        try:
            if not self.mcp_session:
                print("❌ Not connected to MCP server")
                return
            
            logger.info(f"🔧 [MCP CLIENT] Calling get_conversation_history via MCP (session: {self.session_id}, limit: {limit})")
            result = await self.mcp_session.call_tool(
                "get_conversation_history", 
                {"session_id": self.session_id, "limit": limit}
            )
            
            if result.content:
                history_text = result.content[0].text
                logger.info(f"✅ [MCP CLIENT] History received, {len(history_text)} chars")
                
                if "No conversation history found" in history_text:
                    print("📭 No conversation history yet.")
                    return
                
                try:
                    history = json.loads(history_text)
                    print(f"\n📚 Last {len(history)} messages:")
                    print("-" * 50)
                    
                    for msg in history:
                        role_icon = "👤" if msg["role"] == "user" else "🤖"
                        timestamp = msg["timestamp"][:19] if msg["timestamp"] else "unknown"
                        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                        print(f"{role_icon} [{timestamp}] {content}")
                    
                    print("-" * 50)
                    
                except json.JSONDecodeError:
                    print("📚 Recent conversation history:")
                    print(history_text)
            else:
                print("📭 No conversation history yet.")
            
        except Exception as e:
            logger.error(f"❌ [MCP CLIENT] Error retrieving history: {e}")
            print(f"❌ Error retrieving history: {e}")
    
    def show_session_info(self):
        """Show current session information."""
        try:
            sessions = self.session_manager.get_all_sessions()
            current_session = next((s for s in sessions if s["session_id"] == self.session_id), None)
            
            print(f"\n🔍 Session Information:")
            print(f"  Session ID: {self.session_id}")
            
            if current_session:
                print(f"  Messages: {current_session['message_count']}")
                print(f"  First Message: {current_session['first_message']}")
                print(f"  Last Message: {current_session['last_message']}")
            else:
                print("  Status: New session (no messages yet)")
                
            print(f"  Total Sessions: {len(sessions)}")
            print(f"  MCP Connected: {'✅' if self.mcp_session else '❌'}")
            
        except Exception as e:
            print(f"❌ Error getting session info: {e}")
    
    async def discover_capabilities(self) -> dict:
        """Discover available MCP capabilities dynamically."""
        capabilities = {
            "tools": [],
            "prompts": [],
            "resources": []
        }
        
        try:
            # Discover available tools
            tools_result = await self.mcp_session.list_tools()
            capabilities["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
                for tool in tools_result.tools
            ]
            
            # Discover available prompts
            prompts_result = await self.mcp_session.list_prompts()
            capabilities["prompts"] = [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": [arg.dict() for arg in prompt.arguments]
                }
                for prompt in prompts_result
            ]
            
            # Discover available resources
            resources_result = await self.mcp_session.list_resources()
            capabilities["resources"] = [
                {
                    "name": resource.name,
                    "description": resource.description,
                    "type": resource.type
                }
                for resource in resources_result.resources
            ]
            
            logger.info(f"🔍 [MCP CLIENT] Discovered capabilities: {json.dumps(capabilities, indent=2)}")
            return capabilities
            
        except Exception as e:
            logger.error(f"❌ [MCP CLIENT] Error discovering capabilities: {e}")
            return capabilities

    async def create_dynamic_system_prompt(self, capabilities: dict) -> str:
        """Create system prompt using the shared Prompt Registry."""

        from ape.prompts import render_prompt  # lazy import to avoid cycles

        def _fmt(items: list[dict], label: str = "") -> str:
            if not items:
                return f"No {label}available".strip()
            if label:
                label = " " + label
            return "\n".join([f"• **{i['name']}**{label}: {i['description']}" for i in items])

        tools_section = _fmt(capabilities["tools"])
        prompts_section = _fmt(capabilities["prompts"])
        resources_section = (
            "\n".join(
                [
                    f"• **{res['name']}** ({res['type']}): {res['description']}"
                    for res in capabilities["resources"]
                ]
            )
            if capabilities["resources"]
            else "No resources available"
        )

        base_prompt = render_prompt(
            "system",
            {
                "agent_name": "APE",
                "current_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tools_section": tools_section,
                "prompts_section": prompts_section,
                "resources_section": resources_section,
            },
        )

        return base_prompt

    async def chat_with_llm(self, message: str, conversation: list) -> str:
        """Send a message to the LLM with enhanced autonomous capabilities."""
        try:
            # Discover available capabilities
            capabilities = await self.discover_capabilities()
            
            # Create dynamic system prompt
            system_prompt = await self.create_dynamic_system_prompt(capabilities)
            
            # Add session context if available
            context_summary = self.context_manager.get_context_summary()
            if context_summary.strip() != "CURRENT SESSION CONTEXT:":
                system_prompt += f"\n\nCURRENT CONTEXT:\n{context_summary}"
            
            # Increased iteration limits for autonomous operation
            max_iterations = settings.MAX_TOOLS_ITERATIONS
            current_iteration = 0
            cumulative_response = ""
            
            # Initialize conversation with user's message
            execution_conversation = [
                {"role": "system", "content": system_prompt},
                *conversation,
                {"role": "user", "content": message}
            ]
            
            client = ollama.AsyncClient(host=str(settings.OLLAMA_BASE_URL))
            
            while current_iteration < max_iterations:
                current_chunk = ""
                has_tool_calls = False
                
                stream = await client.chat(
                    model=settings.LLM_MODEL,
                    messages=execution_conversation,
                    tools=capabilities["tools"],
                    options={"temperature": settings.TEMPERATURE},
                    stream=True
                )
                
                turn_messages = []
                
                async for chunk in stream:
                    if 'message' in chunk:
                        if chunk['message'].get('content', ''):
                            content = chunk['message']['content']
                            # Print ALL content including thinking - don't filter anything
                            print(content, end="", flush=True)
                            current_chunk += content
                        
                        if chunk['message'].get('tool_calls'):
                            has_tool_calls = True
                            current_iteration += 1
                            
                            # Save the assistant's complete response (including thinking)
                            if current_chunk:
                                turn_messages.append({
                                    "role": "assistant",
                                    "content": current_chunk,
                                    "timestamp": ""
                                })
                                cumulative_response += current_chunk + "\n"
                            
                            # Handle tools with enhanced context
                            tool_results = await self.handle_tool_calls(chunk['message']['tool_calls'])
                            print("\n" + tool_results)
                            
                            turn_messages.append({
                                "role": "tool", 
                                "content": tool_results,
                                "timestamp": ""
                            })
                            
                            # Add tool response to conversation for LLM to continue reasoning
                            execution_conversation.extend([
                                {"role": "assistant", "content": current_chunk},
                                {"role": "tool", "content": tool_results}
                            ])
                            
                            # Let the LLM continue naturally - no forced prompts
                            # The LLM will decide what to do next based on the tool results
                            
                            current_chunk = ""
                            break
                
                if not has_tool_calls:
                    # Final response - save it
                    if current_chunk:
                        cumulative_response += current_chunk
                        turn_messages.append({
                            "role": "assistant",
                            "content": current_chunk,
                            "timestamp": ""
                        })
                    break
                
                if current_iteration >= max_iterations:
                    warning = "\n\n[Note: Reached maximum iteration limit. Task may require continuation.]"
                    print(warning)
                    cumulative_response += warning
                    turn_messages.append({
                        "role": "assistant",
                        "content": warning,
                        "timestamp": ""
                    })
                    break
            
            # Save complete conversation including thinking process
            # Get existing history and append current turn
            existing_history = self.session_manager.get_history(self.session_id)
            current_turn = [
                {"role": "user", "content": message, "timestamp": ""},
                *turn_messages
            ]
            all_messages = existing_history + current_turn
            self.session_manager.save_messages(self.session_id, all_messages)
            
            print()
            return cumulative_response
                
        except Exception as e:
            logger.error(f"💥 [MCP CLIENT] Error in chat_with_llm: {e}")
            return f"I encountered an error while processing your request: {str(e)}"
    
    async def get_ollama_tools(self) -> list:
        """Get tools in Ollama format."""
        if not self.mcp_session:
            return []
        
        try:
            tools_result = await self.mcp_session.list_tools()
            ollama_tools = []
            
            for tool in tools_result.tools:
                ollama_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                ollama_tools.append(ollama_tool)
            
            return ollama_tools
            
        except Exception as e:
            logger.error(f"Error getting Ollama tools: {e}")
            return []
    
    async def handle_tool_calls(self, tool_calls: list) -> str:
        """Handle tool calls from the LLM using MCP protocol with streaming support."""
        if not self.mcp_session:
            return "Sorry, I'm not connected to the MCP server right now."
        
        try:
            results = []
            
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                
                # Check if we can substitute extracted values for placeholders
                if isinstance(arguments, dict):
                    for key, value in arguments.items():
                        if isinstance(value, str):
                            # Replace common placeholders with actual values
                            if value == "retrieved_session_id" and "last_session_id" in self.context_manager.extracted_values:
                                arguments[key] = self.context_manager.extracted_values["last_session_id"]
                                logger.info(f"🔄 [MCP CLIENT] Substituted {value} with {arguments[key]}")
                            elif value == "last_count" and "last_count" in self.context_manager.extracted_values:
                                arguments[key] = self.context_manager.extracted_values["last_count"]
                                logger.info(f"🔄 [MCP CLIENT] Substituted {value} with {arguments[key]}")
                
                # Auto-substitute current session ID for interaction tools if not provided
                if function_name in ["get_last_N_user_interactions", "get_last_N_tool_interactions", "get_last_N_agent_interactions"]:
                    if "session_id" not in arguments or not arguments.get("session_id"):
                        arguments["session_id"] = self.context_manager.current_session_id
                        logger.info(f"🔄 [MCP CLIENT] Auto-substituted current session ID: {arguments['session_id']}")
                
                logger.info(f"🔧 [MCP CLIENT] Executing tool: {function_name} with args: {arguments}")
                
                # Call the MCP tool
                result = await self.mcp_session.call_tool(function_name, arguments)
                
                if result.content:
                    tool_result = result.content[0].text
                    results.append({
                        "tool": function_name,
                        "arguments": arguments,
                        "result": tool_result
                    })
                    
                    # Add to context manager for value extraction
                    self.context_manager.add_tool_result(function_name, arguments, tool_result)
                    
                    logger.info(f"✅ [MCP CLIENT] Tool {function_name} executed successfully")
                else:
                    results.append({
                        "tool": function_name,
                        "arguments": arguments,
                        "result": "No results returned"
                    })
            
            # Format results with validation and error detection
            formatted_response = "🔧 Tool Execution Results:\n\n"
            has_valid_data = False
            
            for idx, result in enumerate(results, 1):
                formatted_response += f"**Tool {idx}: {result['tool']}**\n"
                formatted_response += f"Arguments: {result['arguments']}\n"
                
                # Validate tool result and detect issues
                tool_result = result['result']
                is_error = any(indicator in tool_result.lower() for indicator in [
                    "error", "failed", "exception", "no results found", "rows affected: -1"
                ])
                
                if is_error:
                    formatted_response += f"⚠️ **ISSUE DETECTED**: {tool_result}\n"
                    formatted_response += "❗ This tool did not return valid data. Do not use invented data.\n\n"
                else:
                    formatted_response += f"Result: {tool_result}\n\n"
                    has_valid_data = True
            
            # Add explicit warning if no valid data was obtained
            if not has_valid_data:
                formatted_response += """
🚨 **CRITICAL WARNING**: None of the tools returned valid data.
- DO NOT invent or assume any numbers, facts, or information
- Inform the user about the tool execution issues
- Ask for help debugging the problem or suggest alternative approaches
- NEVER present made-up data as if it came from the tools
"""
            
            # Add key extracted values that might be useful for next steps
            key_values = {}
            for key, value in self.context_manager.extracted_values.items():
                if key in ["last_session_id", "last_message_count", "total_messages", "total_sessions"]:
                    key_values[key] = value
            
            if key_values:
                formatted_response += "📊 Key Values Available:\n"
                for key, value in key_values.items():
                    formatted_response += f"- {key}: {value}\n"
                formatted_response += "\n"
            
            logger.info(f"✅ [MCP CLIENT] Successfully executed {len(results)} tools")
            return formatted_response
                
        except Exception as e:
            logger.error(f"❌ [MCP CLIENT] Error handling tool calls: {e}")
            return f"I encountered an error while using tools: {str(e)}"
    
    async def show_tools(self):
        """Show available MCP tools."""
        await self.list_tools()  # Reuse existing list_tools implementation
    
    def clear_context(self):
        """Clear the current session context."""
        self.context_manager.clear()
        print("🧹 Session context cleared.")
    
    def show_help(self):
        """Display help information."""
        print("""
🤖 APE (Agentic Protocol Executor) - Enhanced Autonomous Agent

Available commands:
  /help     - Show this help
  /history  - Show conversation history  
  /session  - Show session info
  /tools    - List available MCP tools
  /context  - Show current session context
  /clear    - Clear screen
  /reset    - Clear session context
  /quit     - Exit chat
  /exit     - Exit chat
  /q        - Exit chat

🚀 Enhanced Autonomous Capabilities:
The agent can now handle complex multi-step tasks naturally by:
• Thinking through problems step-by-step
• Chaining multiple tool calls automatically
• Building upon previous results
• Completing comprehensive analysis tasks

Try complex requests like:
• "Get database info, find a random session and analyze its conversation patterns"
• "Search for recent tool usage and compare it with user activity patterns"
• "Analyze the database structure and provide insights about conversation trends"
• "Find the most active sessions and summarize their content"

The agent will use its natural reasoning to break down complex tasks!
""")

    async def show_context(self):
        """Show current session context."""
        context_summary = self.context_manager.get_context_summary()
        print("\n" + "="*60)
        print("📋 SESSION CONTEXT")
        print("="*60)
        print(context_summary)
        print("="*60)
    
    async def run(self):
        """Main chat loop."""
        self.print_banner()
        
        # Connect to MCP server
        if not await self.connect_to_mcp():
            print("❌ Cannot continue without MCP server connection")
            return
        
        try:
            while True:
                try:
                    if self.prompt is not None:
                        # prompt_toolkit's async variant avoids nested event-loop issues
                        user_input = (await self.prompt.prompt_async("\nYou: ")).strip()
                    else:
                        user_input = input("\nYou: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        if user_input == '/quit' or user_input == '/exit' or user_input == '/q':
                            break
                        elif user_input == '/help':
                            self.show_help()
                        elif user_input == '/history':
                            await self.show_history()
                        elif user_input == '/session':
                            self.show_session_info()
                        elif user_input == '/tools':
                            await self.show_tools()
                        elif user_input == '/clear':
                            print("\033[2J\033[H")
                        elif user_input == '/context':
                            await self.show_context()
                        elif user_input == '/reset':
                            self.clear_context()
                        continue
                    
                    # Process regular message
                    print("🤖 APE: ", end="", flush=True)
                    
                    # Get conversation history for context
                    conversation = []
                    try:
                        history = self.session_manager.get_history(self.session_id)
                        for msg in history:
                            conversation.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                    except Exception as e:
                        logger.warning(f"Could not retrieve history: {e}")
                    
                    response = await self.chat_agent.chat_with_llm(user_input, conversation)
                    
                    # Save user + assistant turn in history
                    try:
                        existing_history = self.session_manager.get_history(self.session_id)
                        turn = [
                            {"role": "user", "content": user_input, "timestamp": ""},
                            {"role": "assistant", "content": response, "timestamp": ""},
                        ]
                        self.session_manager.save_messages(self.session_id, existing_history + turn)
                    except Exception as e:
                        logger.error(f"Error saving chat history: {e}")
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Chat interrupted. Use /quit or /exit or /q to exit gracefully.")
                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    logger.error(f"Chat error: {e}")
        
        finally:
            await self.disconnect_from_mcp()


async def main():
    """Main entry point for the CLI chat."""
    # Configure logging
    logger.remove()  # Remove default handler
    logger.add("logs/cli_chat.log", rotation="1 day", retention="7 days")
    
    print("🚀 Starting APE CLI Chat with MCP...")
    
    # Check if Ollama is available
    try:
        client = ollama.Client(host=str(settings.OLLAMA_BASE_URL))
        models = client.list()
        if not models.get('models'):
            print("⚠️  Warning: No Ollama models found. Make sure Ollama is running and has models installed.")
            print("   Try: ollama pull gemma3:4b")
    except Exception as e:
        print(f"⚠️  Warning: Could not connect to Ollama: {e}")
        print("   Make sure Ollama is running at http://localhost:11434")
    
    # Start the chat interface
    chat = APEChatCLI()
    await chat.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error in CLI: {e}")
        print(f"❌ Fatal error: {e}")
        sys.exit(1) 