from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class ExecuteDatabaseQueryRequest(BaseModel):
    """Validated payload for :pyfunc:`execute_database_query` tool.

    The new contract expects **only** the field ``query``.  The legacy
    alias ``sql_query`` has been removed to avoid ambiguity that caused the model
    to emit duplicate parameters (``sql`` + ``sql_query``) in tool calls.
    """

    query: str = Field(..., description="Read-only SELECT statement to execute")

    @property
    def normalized_query(self) -> str:
        return self.query.strip()


class ExecuteDatabaseQueryResponse(BaseModel):
    result: str


class ConversationHistoryRequest(BaseModel):
    session_id: Optional[str] = None
    limit: int = 10


class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime


class ConversationHistoryResponse(BaseModel):
    messages: List[Message]


class SearchConversationsRequest(BaseModel):
    query: str
    limit: int = 5


class GenericTextResponse(BaseModel):
    result: str


# ---------------------------------------------------------------------------
# 🆕  Formalised internal envelope models
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    """Represents a request issued by the agent / LLM to call a tool."""

    name: str = Field(..., description="Registered tool name (unique id)")
    arguments: dict = Field(default_factory=dict, description="JSON-serialisable arguments object")


class ToolResult(BaseModel):
    """Normalised result record returned by a tool.

    These objects can be persisted (e.g. to the *history* table) or sent across
    the wire as JSON.  They intentionally mirror the fields used throughout
    :pyclass:`ape.cli.context_manager.ContextManager` so the agent can parse
    them consistently.
    """

    tool: str = Field(..., description="Tool name that produced the result")
    arguments: dict = Field(default_factory=dict, description="Arguments that were passed to the tool")
    result: str = Field(..., description="Raw result payload – often JSON or plain text")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorEnvelope(BaseModel):
    """Structured error payload that can wrap failed tool executions."""

    error: str = Field(..., description="Short error message / summary")
    details: Optional[str] = Field(None, description="Extended error information / traceback")
    tool: Optional[str] = Field(None, description="Tool involved, if any")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request: Optional[ToolCall] = Field(None, description="Original tool-call that triggered the error (if available)") 