#!/usr/bin/env python3
"""
Interactive CLI Chat Client for APE MCP Server

This provides a simple command-line interface to chat with the local LLM
while maintaining conversation history.
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server import chat_with_llm, get_conversation_history, search_conversations
from loguru import logger

class ChatCLI:
    def __init__(self):
        self.session_id = f"cli-session-{uuid.uuid4().hex[:8]}"
        self.running = True
        
    def print_welcome(self):
        """Print welcome message and instructions."""
        print("🤖 APE Chat CLI - Interactive Mode")
        print("=" * 50)
        print(f"Session ID: {self.session_id}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("Commands:")
        print("  /help     - Show this help message")
        print("  /history  - Show conversation history") 
        print("  /search   - Search conversation history")
        print("  /clear    - Start a new session")
        print("  /quit     - Exit the chat")
        print("  <message> - Chat with the AI")
        print("-" * 50)
        print()

    def print_help(self):
        """Print help information."""
        print("\n📖 Available Commands:")
        print("  /help              - Show this help message")
        print("  /history [limit]   - Show recent messages (default: 10)")
        print("  /search <query>    - Search for messages containing text")
        print("  /clear             - Start a new conversation session")
        print("  /quit, /exit       - Exit the chat")
        print("  <message>          - Send message to AI")
        print()

    async def handle_history(self, args):
        """Handle /history command."""
        try:
            limit = int(args[0]) if args else 10
            print(f"\n📚 Last {limit} messages:")
            history = await get_conversation_history(self.session_id, limit)
            
            import json
            messages = json.loads(history)
            
            if not messages:
                print("  No conversation history found.")
                return
                
            for msg in messages[-limit:]:
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                timestamp = msg.get("timestamp", "")
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                print(f"  {role_emoji} [{timestamp}] {content}")
                
        except Exception as e:
            print(f"❌ Error retrieving history: {e}")

    async def handle_search(self, args):
        """Handle /search command."""
        if not args:
            print("❌ Please provide a search query. Usage: /search <query>")
            return
            
        query = " ".join(args)
        try:
            print(f"\n🔍 Searching for: '{query}'")
            results = await search_conversations(query, 5)
            
            import json
            matches = json.loads(results)
            
            if isinstance(matches, list) and matches:
                print(f"Found {len(matches)} matches:")
                for i, match in enumerate(matches, 1):
                    role_emoji = "👤" if match["role"] == "user" else "🤖"
                    content = match["content"][:150] + "..." if len(match["content"]) > 150 else match["content"]
                    print(f"  {i}. {role_emoji} {content}")
            else:
                print("  No matches found.")
                
        except Exception as e:
            print(f"❌ Error searching: {e}")

    def handle_clear(self):
        """Handle /clear command."""
        self.session_id = f"cli-session-{uuid.uuid4().hex[:8]}"
        print(f"🔄 Started new session: {self.session_id}")

    async def handle_chat(self, message):
        """Handle regular chat messages."""
        try:
            print("🤖 Thinking...")
            response = await chat_with_llm(
                message=message,
                session_id=self.session_id,
                include_history=True
            )
            print(f"🤖 {response}")
            
        except Exception as e:
            print(f"❌ Error: {e}")

    async def run(self):
        """Main chat loop."""
        self.print_welcome()
        
        while self.running:
            try:
                # Get user input
                user_input = input("👤 ").strip()
                
                if not user_input:
                    continue
                    
                # Handle commands
                if user_input.startswith('/'):
                    parts = user_input[1:].split()
                    command = parts[0].lower()
                    args = parts[1:]
                    
                    if command in ['quit', 'exit']:
                        print("👋 Goodbye!")
                        self.running = False
                        
                    elif command == 'help':
                        self.print_help()
                        
                    elif command == 'history':
                        await self.handle_history(args)
                        
                    elif command == 'search':
                        await self.handle_search(args)
                        
                    elif command == 'clear':
                        self.handle_clear()
                        
                    else:
                        print(f"❌ Unknown command: /{command}")
                        print("Type /help for available commands.")
                        
                else:
                    # Regular chat message
                    await self.handle_chat(user_input)
                    
                print()  # Add spacing between interactions
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                self.running = False
                
            except EOFError:
                print("\n👋 Goodbye!")
                self.running = False
                
            except Exception as e:
                print(f"❌ Unexpected error: {e}")


async def main():
    """Main function."""
    # Configure logging to be less verbose for CLI
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    
    chat = ChatCLI()
    await chat.run()


if __name__ == "__main__":
    asyncio.run(main()) 