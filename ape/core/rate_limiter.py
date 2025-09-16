"""Simple in-memory rate-limiter (per session).

The helper keeps a deque of timestamps for each *session_id* and rejects
requests that would exceed *CALLS_PER_MINUTE* within a rolling 60-second
window.  The implementation is deliberately dependency-free and works in a
single-process setup which is sufficient for Milestone-M2.
"""

from collections import defaultdict, deque
from time import time
from typing import Deque, Dict

# Public configuration – can be tweaked via environment later
CALLS_PER_MINUTE: int = 60
WINDOW_SECONDS: int = 60  # rolling window

# Internal state: session_id → deque[timestamps]
_counters: Dict[str, Deque[float]] = defaultdict(deque)


def allow(session_id: str) -> bool:
    """Return *True* when the call is permitted for *session_id*.

    The algorithm removes timestamps older than *WINDOW_SECONDS* from the left
    side of the deque and then checks whether the remaining length is below
    *CALLS_PER_MINUTE*.  O(1) amortised time.
    """

    now = time()
    q = _counters[session_id]

    # Drop expired timestamps
    expire_before = now - WINDOW_SECONDS
    while q and q[0] < expire_before:
        q.popleft()

    if len(q) >= CALLS_PER_MINUTE:
        return False

    q.append(now)
    return True 