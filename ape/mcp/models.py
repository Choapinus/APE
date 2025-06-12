from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class ExecuteDatabaseQueryRequest(BaseModel):
    sql_query: Optional[str] = Field(None, description="Primary SQL query parameter")
    query: Optional[str] = Field(None, description="Alias for sql_query for backwards-compat")

    @property
    def normalized_query(self) -> str:
        return (self.sql_query or self.query or "").strip()


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