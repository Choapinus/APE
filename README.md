# APE: Advanced Prompt Engine MCP Server

APE is a **Model Context Protocol (MCP) server** that provides conversational AI capabilities with persistent memory and database tools. It integrates with local LLMs via Ollama and offers tools for conversation management, database queries, and AI chat functionality.

## Features

- **🔌 MCP Protocol Compatible**: Standard Model Context Protocol server
- **💬 Conversational Memory**: Persistent conversation history with SQLite storage
- **🛠️ Rich Tool Set**: Database queries, conversation search, and LLM chat tools  
- **🔍 MCP Inspector**: Built-in development and debugging interface
- **🤖 Local LLM Integration**: Seamless integration with Ollama models
- **📊 Resource Access**: Conversation data exposed as MCP resources

## Getting Started

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) installed and running
- Node.js 16+ (for MCP Inspector)
- An Ollama model pulled, e.g., `ollama pull gemma2:2b`

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd ape
   ```

2. **Set up Python environment:**
   ```bash
   conda create -n ape python=3.11
   conda activate ape
   pip install -r requirements.txt
   ```

### Configuration

Configure via environment variables or create a `.env` file:

```env
OLLAMA_HOST="http://localhost:11434"
LLM_MODEL="gemma2:2b"
LOG_LEVEL="INFO"
```

### Running the MCP Server

#### Development Mode (with Inspector)

Start the server with the MCP Inspector for development and testing:

```bash
conda activate ape
mcp dev mcp_server.py
```

This will:
- Start the MCP server
- Launch the MCP Inspector at `http://127.0.0.1:6274`
- Provide a web interface to test tools and resources

#### Production Mode

For production use, configure the server in your MCP client:

```bash
conda activate ape
mcp run mcp_server.py
```

### MCP Client Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "ape": {
      "command": "python",
      "args": ["path/to/ape/mcp_server.py"],
      "env": {
        "OLLAMA_HOST": "http://localhost:11434",
        "LLM_MODEL": "gemma2:2b"
      }
    }
  }
}
```

## Available Tools

### 🗣️ `chat_with_llm`
Send messages to the local LLM with conversation context.

**Parameters:**
- `message` (required): Message to send to the LLM
- `session_id` (optional): Session ID for conversation continuity
- `include_history` (optional): Whether to include conversation history (default: true)

### 📚 `get_conversation_history`
Retrieve conversation history from the database.

**Parameters:**
- `session_id` (optional): Specific session to retrieve
- `limit` (optional): Number of messages to retrieve (default: 10)

### 🔍 `search_conversations`
Search through conversation history using text matching.

**Parameters:**
- `query` (required): Text to search for in conversations
- `limit` (optional): Maximum results to return (default: 5)

### 🗄️ `get_database_info`
Get information about the conversation database schema and statistics.

**Parameters:** None

## Available Resources

### 📁 `conversation://sessions`
Overview of all conversation sessions with message counts and metadata.

### ⏰ `conversation://recent`
Most recent conversation messages across all sessions.

## Project Structure

```
ape/
├── mcp_server.py           # Main MCP server implementation
├── ape/                    # Core application modules
│   ├── config.py           # Configuration management
│   ├── session.py          # Session and database management
│   ├── utils.py            # Utility functions
│   └── sessions.db         # SQLite conversation database
├── logs/                   # Application logs
├── tests/                  # Test files
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Development

### Testing

Test the MCP server functions directly:

```bash
conda activate ape
python test_mcp_functions.py
```

Test with MCP Inspector:

```bash
conda activate ape
mcp dev mcp_server.py
# Open http://127.0.0.1:6274 in your browser
```

### Adding New Tools

1. Add a new function with the `@mcp.tool()` decorator in `mcp_server.py`
2. Define clear docstrings and type hints for parameters
3. Test with the MCP Inspector

Example:
```python
@mcp.tool()
async def my_new_tool(param1: str, param2: int = 10) -> str:
    """
    Description of what this tool does.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2 (default: 10)
    """
    # Implementation here
    return "Result"
```

## Integration Examples

### With Claude Desktop

1. Add the server configuration to Claude Desktop's settings
2. Use tools directly in conversations:
   - "Search for messages about Python"
   - "Show me recent conversations"
   - "Chat with the local model about quantum physics"

### With Other MCP Clients

Any MCP-compatible client can connect to APE using the stdio transport:

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async with stdio_client("python", ["mcp_server.py"]) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_database_info", {})
```

## Troubleshooting

### Common Issues

1. **"No module named 'ape'"**: Ensure you're in the correct conda environment
2. **Ollama connection errors**: Verify Ollama is running on the configured host
3. **Node.js not found**: Install Node.js 16+ for MCP Inspector support

### Logs

Check application logs for detailed error information:

```bash
tail -f logs/mcp_server.log
```

## Migration from FastAPI Version

If upgrading from the previous FastAPI-based version:

1. **Backup data**: Your `ape/sessions.db` file contains all conversation history
2. **Update client code**: Replace FastAPI HTTP calls with MCP client calls
3. **Configuration**: Environment variables remain the same

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test with MCP Inspector
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## About

APE provides a bridge between conversational AI and persistent memory using the standardized Model Context Protocol. It enables AI assistants to maintain context across conversations while providing powerful tools for data retrieval and analysis.
