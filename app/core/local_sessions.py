"""Persistent, process-shared sessions for local development without Redis."""
import asyncio
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class LocalSessions:
    def __init__(self, path):
        self.path = Path(path)

    def _execute(self, operation, key=None, value=None, ttl=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (key TEXT PRIMARY KEY, value TEXT, expires REAL)")
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
            if operation == "rate":
                db.execute("INSERT INTO sessions VALUES (?, '1', ?) ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1",
                           (key, now + 60))
                return int(db.execute("SELECT value FROM sessions WHERE key = ?", (key,)).fetchone()[0])
            if operation == "set":
                db.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)",
                           (key, value, now + ttl if ttl is not None else None))
                return True
            if operation == "exists":
                return db.execute("SELECT 1 FROM sessions WHERE key = ?", (key,)).fetchone() is not None
            return True

    async def eval(self, script, count, key):
        # Only the authentication middleware's fixed-window rate counter is supported.
        if count != 1 or not key.startswith("auth-rate:"):
            raise ValueError("Unsupported local session operation")
        return await asyncio.to_thread(self._execute, "rate", key)

    async def set(self, key, value, ex=None):
        return await asyncio.to_thread(self._execute, "set", key, value, ex)

    async def exists(self, key):
        return await asyncio.to_thread(self._execute, "exists", key)

    async def ping(self):
        return await asyncio.to_thread(self._execute, "ping")

    async def aclose(self):
        pass
