from typing import Dict, Any, List
from datetime import datetime
import json
from loguru import logger

"""Context tracking utility used by ChatAgent.

The `ContextManager` stores *verifiable* tool results plus helper values (last
session id, message counts, …) that the LLM can reference later.  It is intentionally
kept runtime-only – it never writes to disk.
"""


class ContextManager:
    """Keep per-session context that survives multiple tool calls.

    Responsibilities
    -----------------
    1. Remember every tool invocation (name, args, result, timestamp).
    2. Extract recurring values (e.g. `last_session_id`) so the LLM can refer to
       them without complex JSON parsing.
    3. Provide a compact **human readable** summary for prompt-stuffing.
    """

    def __init__(self, session_id: str | None = None):
        self.session_data: Dict[str, Any] = {}
        self.tool_results: List[Dict[str, Any]] = []
        self.extracted_values: Dict[str, Any] = {}
        self.current_session_id = session_id

    def add_tool_result(self, tool_name: str, arguments: dict, result: str):
        """Add a tool result and extract key values."""
        tool_result = {
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.tool_results.append(tool_result)

        # Let the LLM extract values from the result
        self._extract_values_from_result(tool_result)

    def _extract_values_from_result(self, tool_result: Dict[str, Any]):
        """Extract and structure tool results for better LLM context."""
        try:
            # Store the raw result for LLM to analyze later
            key = f"{tool_result['tool']}_{len(self.tool_results)}"
            self.session_data[key] = tool_result

            # Store basic metadata
            self.extracted_values[f"{key}_timestamp"] = tool_result["timestamp"]
            self.extracted_values[f"{key}_tool"] = tool_result["tool"]

            # Enhanced value extraction for better LLM context
            if isinstance(tool_result["result"], str):
                try:
                    # Store JSON results if valid
                    data = json.loads(tool_result["result"])
                    self.extracted_values[f"{key}_data"] = data

                    # Extract commonly useful values for LLM context
                    if isinstance(data, list) and len(data) > 0:
                        first_item = data[0]
                        if "session_id" in first_item:
                            self.extracted_values["last_session_id"] = first_item["session_id"]
                        if "message_count" in first_item:
                            self.extracted_values["last_message_count"] = first_item["message_count"]
                        if "total_messages" in first_item:
                            self.extracted_values["total_messages"] = first_item["total_messages"]
                        if "total_sessions" in first_item:
                            self.extracted_values["total_sessions"] = first_item["total_sessions"]
                except json.JSONDecodeError:
                    # Store raw text if not JSON
                    self.extracted_values[f"{key}_text"] = tool_result["result"]

        except Exception as e:
            logger.debug(f"Could not extract values from tool result: {e}")

    def get_context_summary(self) -> str:
        """Get a summary of current context for prompts."""
        summary = "CURRENT SESSION CONTEXT:\n"

        if self.session_data:
            summary += "\nAvailable Tool Results:\n"
            for key, value in self.session_data.items():
                summary += f"- {key}: {value['tool']} (executed at {value['timestamp']})\n"

        if self.extracted_values:
            summary += "\nExtracted Values:\n"
            for key, value in self.extracted_values.items():
                if isinstance(value, str) and len(value) > 100:
                    summary += f"- {key}: {str(value)[:100]}...\n"
                else:
                    summary += f"- {key}: {value}\n"

        return summary

    def clear(self):
        """Clear the context (for new sessions)."""
        self.session_data.clear()
        self.tool_results.clear()
        self.extracted_values.clear() 