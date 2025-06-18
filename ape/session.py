"""Deprecated compatibility module.

`ape.session` is retained solely for backward compatibility with existing
imports (tests, third-party code).  All logic now lives in
:pyfile:`ape.mcp.session_manager`.  Importing from this module re-exports the
canonical async-first `SessionManager` and its `get_session_manager()` helper.
"""

from warnings import warn

from ape.mcp.session_manager import SessionManager, get_session_manager  # noqa: F401

warn(
    "`ape.session` is deprecated – import from `ape.mcp.session_manager` instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["SessionManager", "get_session_manager"] 