"""Run against a disposable PostgreSQL database, never a live banking database."""
import asyncio
import os
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.database import Base
from app.models import Transaction, LedgerEntry
from app.services.transfer_service import TransferService
from app.services.transaction_service import TransactionService
from app.services.ledger_service import LedgerService
from tests.helpers import funded
from uuid import uuid4

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not set")]


@pytest.fixture
async def pg_factory():
    # A random schema prevents touching pre-existing tables, even in a shared test database.
    schema = "test_" + uuid4().hex
    root = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with root.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], connect_args={"server_settings":{"search_path":schema}})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in Path("alembic/versions/invariants.sql").read_text().split("-- SPLIT"):
            if statement.strip(): await conn.execute(text(statement))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()
    async with root.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await root.dispose()


async def test_concurrent_duplicate_and_overdraft(pg_factory):
    async with pg_factory() as db:
        source,dest,_,_=await funded(db,"1000")
        source_id,dest_id=source.id,dest.id
    async def transfer(key,amount):
        async with pg_factory() as db:
            try:
                txn=await TransferService.transfer(db,source_id,dest_id,Decimal(amount),idempotency_key=key)
                await db.commit()
                return txn.id
            except ValueError:
                await db.rollback()
                return None
    duplicates=await asyncio.gather(*(transfer("same","100") for _ in range(8)))
    assert len(set(duplicates))==1 and duplicates[0] is not None
    competing=await asyncio.gather(transfer("a","800"),transfer("b","800"))
    assert sum(x is not None for x in competing)==1
    async with pg_factory() as db:
        assert await LedgerService.get_account_balance(db,source_id)==Decimal("91")


async def test_database_guards_and_double_reversal(pg_factory):
    async with pg_factory() as db:
        source,dest,_,_=await funded(db)
        txn=await TransferService.transfer(db,source.id,dest.id,Decimal("100"),idempotency_key="original")
        await db.commit()
        txn_id=txn.id
        with pytest.raises(Exception,match="immutable"):
            await db.execute(text("UPDATE ledger_entries SET amount=amount+1"))
        await db.rollback()
        with pytest.raises(Exception,match="immutable"):
            await db.execute(text("UPDATE transactions SET amount=amount+1"))
        await db.rollback()
    async def reverse():
        async with pg_factory() as db:
            try:
                row=await TransactionService.reverse(db,txn_id,uuid4(),"Concurrent test")
                await db.commit()
                return row.id
            except ValueError:
                await db.rollback()
                return None
    results=await asyncio.gather(reverse(),reverse())
    assert sum(x is not None for x in results)==1
