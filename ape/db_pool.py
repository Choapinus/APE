from __future__ import annotations

"""Simple asyncio connection pool for *aiosqlite*.

This lightweight helper avoids paying the open/close penalty for every query
and keeps at most *size* file handles alive.  All callers should use the
``get_db()`` async context manager:

```python
async with get_db() as conn:
    await conn.execute(...)
```
"""

from asyncio import Queue
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite

from ape.settings import settings


class _AioSqlitePool:
    def __init__(self, db_path: str, size: int = 5):
        self.db_path = db_path
        self._size = size
        self._queue: Queue[aiosqlite.Connection] = Queue(maxsize=size)
        self._initialised = False

    async def _init_pool(self) -> None:
        """Open *size* connections and put them into the queue."""
        if self._initialised:
            return
        # ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        for _ in range(self._size):
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL")
            await self._queue.put(conn)
        self._initialised = True

    async def acquire(self) -> aiosqlite.Connection:  # noqa: D401 – simple getter
        if not self._initialised:
            await self._init_pool()
        return await self._queue.get()

    async def release(self, conn: aiosqlite.Connection) -> None:  # noqa: D401 – simple helper
        await self._queue.put(conn)

    async def close(self) -> None:
        while not self._queue.empty():
            conn = await self._queue.get()
            await conn.close()
        self._initialised = False


_POOL: Optional[_AioSqlitePool] = None


def get_pool() -> _AioSqlitePool:  # noqa: D401 – singleton accessor
    global _POOL
    if _POOL is None:
        _POOL = _AioSqlitePool(settings.SESSION_DB_PATH, size=5)
    return _POOL


@asynccontextmanager
async def get_db():  # noqa: D401 – async context manager
    pool = get_pool()
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn) 