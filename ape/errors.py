from __future__ import annotations

"""Centralised error types for APE.

Each custom error is JSON-serialisable via ``to_dict`` so tool envelopes and
APIs can expose machine-readable diagnostics instead of free-form strings.
"""

from typing import Any, Dict, Optional


class ApeError(Exception):
    """Base class for all structured APE exceptions."""

    code: str = "APE_ERROR"
    status: str = "error"

    def __init__(self, message: str, *, data: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401 – simple init
        super().__init__(message)
        self.message = message
        self.data = data or {}

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:  # noqa: D401 – utility
        return {
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "data": self.data,
        }

    def __str__(self) -> str:  # noqa: D401 – friendly repr
        return f"{self.code}: {self.message}"


class DatabaseError(ApeError):
    code = "SQL_ERROR"


class ToolExecutionError(ApeError):
    code = "TOOL_EXECUTION_ERROR" 