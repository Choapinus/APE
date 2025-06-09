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
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from loguru import logger
import ollama

from ape.mcp.session_manager import get_session_manager


class APEChatCLI:
    """Command-line interface for APE chat functionality using MCP."""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.session_manager = get_session_manager()
        self.mcp_session: Optional[ClientSession] = None
        logger.info(f"Started new chat session: {self.session_id}")
    
    def print_banner(self):
        """Print the APE CLI banner."""
        print("\n" + "="*60)
        print("🤖 APE (Advanced Prompt Engine) - CLI Chat")
        print("="*60)
        print("Session ID:", self.session_id[:8] + "...")
        print("\nCommands:")
        print("  /help     - Show this help")
        print("  /history  - Show conversation history")
        print("  /session  - Show session info")
        print("  /tools    - List available MCP tools")
        print("  /clear    - Clear screen")
        print("  /quit     - Exit chat")
        print("\n🧠 Intelligence: Connected to MCP server with tools:")
        print("  • Database tools for conversation management")
        print("  • Search tools for finding content")
        print("  • History tools for context retrieval")
        print("="*60 + "\n")
    
    async def connect_to_mcp_server(self):
        """Connect to the MCP server."""
        try:
            # Create server parameters for stdio connection
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_server.py"],
                env=None,
            )
            
            # Connect to the server
            self.stdio_client = stdio_client(server_params)
            read, write = await self.stdio_client.__aenter__()
            
            # Create session
            self.mcp_session = ClientSession(read, write)
            await self.mcp_session.__aenter__()
            
            # Initialize the connection
            await self.mcp_session.initialize()
            
            logger.info("Connected to MCP server successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            print(f"❌ Failed to connect to MCP server: {e}")
            return False
    
    async def disconnect_from_mcp_server(self):
        """Disconnect from the MCP server."""
        try:
            if self.mcp_session:
                await self.mcp_session.__aexit__(None, None, None)
            if hasattr(self, 'stdio_client'):
                await self.stdio_client.__aexit__(None, None, None)
        except Exception as e:
            logger.error(f"Error disconnecting from MCP server: {e}")
    
    async def list_tools(self):
        """List available MCP tools."""
        try:
            if not self.mcp_session:
                print("❌ Not connected to MCP server")
                return
                
            tools_result = await self.mcp_session.list_tools()
            print(f"\n🔧 Available MCP Tools ({len(tools_result.tools)}):")
            print("-" * 50)
            
            for tool in tools_result.tools:
                print(f"• {tool.name}: {tool.description}")
                
            print("-" * 50)
            
        except Exception as e:
            print(f"❌ Error listing tools: {e}")
    
    async def show_history(self, limit: int = 10):
        """Show conversation history using MCP."""
        try:
            if not self.mcp_session:
                print("❌ Not connected to MCP server")
                return
                
            result = await self.mcp_session.call_tool(
                "get_conversation_history", 
                {"session_id": self.session_id, "limit": limit}
            )
            
            if result.content:
                history_text = result.content[0].text
                
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
    
    async def chat_with_llm(self, message: str) -> str:
        """Chat with LLM using proper MCP tool calling."""
        try:
            # Get conversation history
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
            
            # Add current message
            conversation.append({
                "role": "user",
                "content": message
            })
            
            # Create system prompt with MCP tools
            system_prompt = await self.create_system_prompt()
            
            # Call Ollama
            client = ollama.AsyncClient(host="http://localhost:11434")
            
            try:
                # Try with tools first (for models that support it)
                tools = await self.get_ollama_tools()
                
                response = await client.chat(
                    model="gemma3:4b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *conversation
                    ],
                    tools=tools if tools else None
                )
                
                assistant_response = response['message']['content']
                
                # Handle tool calls if present
                if response['message'].get('tool_calls'):
                    assistant_response = await self.handle_tool_calls(
                        response['message']['tool_calls'], 
                        assistant_response
                    )
                
            except Exception as e:
                if "does not support tools" in str(e):
                    # Fallback for models without tool support
                    logger.info("Model doesn't support tools, using fallback approach")
                    
                    # Check if user is asking for specific data that needs tools
                    response_text = await self.handle_fallback_chat(message, conversation, system_prompt, client)
                    assistant_response = response_text
                else:
                    raise e
            
            # Save conversation
            self.session_manager.save_messages(self.session_id, [
                {"role": "user", "content": message, "timestamp": ""},
                {"role": "assistant", "content": assistant_response, "timestamp": ""}
            ])
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"❌ Error processing your message: {str(e)}"
    
    async def create_system_prompt(self) -> str:
        """Create system prompt with MCP tool information."""
        if not self.mcp_session:
            return "You are APE, an AI assistant."
        
        try:
            tools_result = await self.mcp_session.list_tools()
            tools_text = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools_result.tools])
            
            return f"""You are APE (Advanced Prompt Engine), an AI assistant with access to conversation management tools through MCP.

Available tools:
{tools_text}

Use these tools intelligently to help users with:
- Retrieving conversation history
- Searching through past conversations  
- Getting database information
- Executing custom database queries

Be conversational and helpful. Only use tools when they add value to your response."""
        
        except Exception as e:
            logger.error(f"Error creating system prompt: {e}")
            return "You are APE, an AI assistant."
    
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
    
    async def handle_tool_calls(self, tool_calls: list, response: str) -> str:
        """Handle tool calls from Ollama."""
        if not self.mcp_session:
            return response
        
        try:
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                
                # Call the MCP tool
                result = await self.mcp_session.call_tool(function_name, arguments)
                
                if result.content:
                    tool_result = result.content[0].text
                    response += f"\n\n🔧 **Tool Result ({function_name}):**\n{tool_result}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling tool calls: {e}")
            return response + f"\n\n❌ Error executing tools: {str(e)}"
    
    async def handle_fallback_chat(self, message: str, conversation: list, system_prompt: str, client) -> str:
        """Handle chat for models that don't support tools."""
        
        # Check if the user is asking for data that requires tools
        message_lower = message.lower()
        
        # Handle specific requests that need MCP tools
        if any(keyword in message_lower for keyword in ['database', 'db info', 'schema', 'tables']):
            if self.mcp_session:
                try:
                    result = await self.mcp_session.call_tool('get_database_info', {})
                    if result.content:
                        db_info = result.content[0].text
                        return f"Here's the database information:\n\n{db_info}"
                except Exception as e:
                    logger.error(f"Error getting database info: {e}")
        
        elif any(keyword in message_lower for keyword in ['history', 'conversation', 'messages', 'previous']):
            if self.mcp_session:
                try:
                    result = await self.mcp_session.call_tool('get_conversation_history', 
                                                            {"session_id": self.session_id, "limit": 5})
                    if result.content:
                        history_info = result.content[0].text
                        return f"Here's our recent conversation history:\n\n{history_info}"
                except Exception as e:
                    logger.error(f"Error getting history: {e}")
        
        elif any(keyword in message_lower for keyword in ['search', 'find', 'look for']):
            # Extract search query
            query_words = message_lower.split()
            if 'for' in query_words:
                for_idx = query_words.index('for')
                if for_idx + 1 < len(query_words):
                    search_query = ' '.join(query_words[for_idx + 1:])
                    if self.mcp_session:
                        try:
                            result = await self.mcp_session.call_tool('search_conversations', 
                                                                    {"query": search_query, "limit": 5})
                            if result.content:
                                search_results = result.content[0].text
                                return f"Search results for '{search_query}':\n\n{search_results}"
                        except Exception as e:
                            logger.error(f"Error searching: {e}")
        
        # Default chat response
        enhanced_prompt = system_prompt + f"""

Current user message: "{message}"

Respond naturally and conversationally. If the user is asking about:
- Database information: Mention that you can provide database schema and statistics
- Conversation history: Mention that you can show previous messages  
- Searching conversations: Mention that you can search through past conversations
- Tool capabilities: List the 4 available tools: execute_database_query, get_conversation_history, get_database_info, search_conversations

Be helpful and suggest using /tools command to see available MCP tools."""
        
        response = await client.chat(
            model="gemma3:4b",
            messages=[
                {"role": "system", "content": enhanced_prompt},
                *conversation
            ]
        )
        
        return response['message']['content']
    
    async def run(self):
        """Run the interactive chat loop."""
        self.print_banner()
        
        # Connect to MCP server
        if not await self.connect_to_mcp_server():
            print("❌ Cannot continue without MCP server connection")
            return
        
        print("✅ Connected to MCP server successfully!")
        
        try:
            while True:
                try:
                    # Get user input
                    user_input = input("\nYou: ").strip()
                    
                    # Handle empty input
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        await self.handle_command(user_input)
                        continue
                    
                    # Process regular message
                    print("🤖 APE: ", end="", flush=True)
                    response = await self.chat_with_llm(user_input)
                    print(response)
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Chat interrupted. Use /quit to exit gracefully.")
                    continue
                except EOFError:
                    print("\n\n👋 Goodbye!")
                    break
                    
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            print(f"❌ Fatal error: {e}")
        finally:
            await self.disconnect_from_mcp_server()
    
    async def handle_command(self, command: str):
        """Handle CLI commands."""
        cmd = command.lower().split()[0]
        
        if cmd == '/help':
            self.print_banner()
            
        elif cmd == '/history':
            await self.show_history()
            
        elif cmd == '/session':
            self.show_session_info()
            
        elif cmd == '/tools':
            await self.list_tools()
            
        elif cmd == '/clear':
            # Clear screen
            import os
            os.system('clear' if os.name == 'posix' else 'cls')
            self.print_banner()
            
        elif cmd == '/quit':
            print("👋 Goodbye!")
            await self.disconnect_from_mcp_server()
            sys.exit(0)
            
        else:
            print(f"❓ Unknown command: {command}")
            print("Type /help for available commands.")


async def main():
    """Main entry point for the CLI chat."""
    # Configure logging
    logger.remove()  # Remove default handler
    logger.add("logs/cli_chat.log", rotation="1 day", retention="7 days")
    
    print("🚀 Starting APE CLI Chat with MCP...")
    
    # Check if Ollama is available
    try:
        client = ollama.Client(host="http://localhost:11434")
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