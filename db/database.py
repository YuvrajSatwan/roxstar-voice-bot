"""Async database engine management.

``DATABASE_URL`` selects the backend:
  * unset                              -> local SQLite file ``./sts_lab.db``
  * ``sqlite+aiosqlite:///./x.db``     -> SQLite
  * ``postgresql://user:pw@host/db``   -> PostgreSQL (rewritten to asyncpg)

LiveKit may run each job in its own thread with its own event loop, and async
engines must not be shared across loops. ``acquire_database`` therefore keeps
one ``Database`` per (event loop, URL) with reference counting.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

logger = logging.getLogger("sts_db")

# Anchored to the project folder (not the current directory) so the worker and the
# token server always open the same file no matter where they were started from.
DEFAULT_DB_FILE = Path(__file__).resolve().parent.parent / "sts_lab.db"
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{DEFAULT_DB_FILE.as_posix()}"


def resolve_database_url(url: str | None = None) -> str:
    raw = (url or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL).strip()
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]
    elif raw.startswith("sqlite://") and not raw.startswith("sqlite+"):
        raw = "sqlite+aiosqlite://" + raw[len("sqlite://"):]
    return raw


def redact_url(url: str) -> str:
    """Hide the password when logging a database URL."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.rsplit("@", 1)
        if ":" in creds:
            creds = creds.split(":", 1)[0] + ":***"
        return f"{scheme}://{creds}@{host}"
    return url


class Database:
    def __init__(self, url: str | None = None) -> None:
        self.url = resolve_database_url(url)
        self.is_sqlite = self.url.startswith("sqlite")
        kwargs: dict = {}
        if self.is_sqlite:
            kwargs["connect_args"] = {"timeout": 30}
        else:
            kwargs.update(pool_size=3, max_overflow=2, pool_pre_ping=True)
        self.engine: AsyncEngine = create_async_engine(self.url, **kwargs)
        if self.is_sqlite:
            @event.listens_for(self.engine.sync_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record) -> None:  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        self._sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def ensure_schema(self) -> None:
        """Create tables once. Retried on the next call if the database is unreachable."""
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self._schema_ready = True
            logger.info("Database schema ready (%s)", redact_url(self.url))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        await self.ensure_schema()
        async with self._sessionmaker() as s:
            try:
                yield s
            except Exception:
                await s.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()


_registry: dict[tuple[int, str], list] = {}


async def acquire_database(url: str | None = None) -> Database:
    """Return the Database for the running event loop, creating it if needed."""
    resolved = resolve_database_url(url)
    key = (id(asyncio.get_running_loop()), resolved)
    entry = _registry.get(key)
    if entry is None:
        entry = [Database(resolved), 0]
        _registry[key] = entry
    entry[1] += 1
    return entry[0]


async def release_database(db: Database) -> None:
    key = (id(asyncio.get_running_loop()), db.url)
    entry = _registry.get(key)
    if entry is None or entry[0] is not db:
        return
    entry[1] -= 1
    if entry[1] <= 0:
        _registry.pop(key, None)
        try:
            await db.dispose()
        except Exception as exc:  # pragma: no cover
            logger.debug("Database dispose failed: %s", exc)
