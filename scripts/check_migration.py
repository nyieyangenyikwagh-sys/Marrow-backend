"""Smoke-test a fresh migration and seed without contacting external services."""
import asyncio
import os
from pathlib import Path
from uuid import uuid4

path = Path("test-results") / f"migration-{uuid4().hex}.db"
path.parent.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{path.as_posix()}"
from alembic.config import Config
from alembic import command
command.upgrade(Config("alembic.ini"), "head")

from scripts.seed import seed
from app.core.database import engine, AsyncSessionLocal
from sqlalchemy import text


async def verify():
    await seed("LocalSmokeTestOnly123!", demo=True)
    await seed("LocalSmokeTestOnly123!", demo=True)
    async with AsyncSessionLocal() as db:
        count = await db.scalar(text("SELECT count(*) FROM transactions"))
        assert count == 4, f"Seed duplicated funding: {count}"
        total = await db.scalar(text("SELECT sum(CASE WHEN entry_type='CREDIT' THEN amount ELSE -amount END) FROM ledger_entries"))
        assert total == 0
        try:
            await db.execute(text("UPDATE ledger_entries SET amount=1"))
        except Exception as exc:
            assert "Immutable record" in str(exc)
            await db.rollback()
        else:
            raise AssertionError("Database immutability trigger did not fire")
    await engine.dispose()
    print("Fresh migration, repeatable seed, balanced funding, and database immutability verified.")


asyncio.run(verify())
