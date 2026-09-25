import os
from pathlib import Path
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test-placeholder.db"
os.environ["SECRET_KEY"] = "test-secret-" * 6
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["ENVIRONMENT"] = "test"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import event
from app.core.database import Base, get_db
from app.main import app as api_app
import app.models


class FakeRedis:
    def __init__(self): self.values = {}
    async def get(self, key): return self.values.get(key)
    async def set(self, key, value, **kwargs): self.values[key] = value; return True
    async def exists(self, key): return key in self.values
    async def eval(self, script, count, key): return 1
    async def ping(self): return True


@pytest.fixture(autouse=True)
def redis(monkeypatch):
    cache = FakeRedis()
    async def get(): return cache
    monkeypatch.setattr("app.services.auth_service.get_redis", get)
    monkeypatch.setattr("app.main.client", cache)
    monkeypatch.setattr("app.core.redis.client", cache)
    return cache


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bank.db'}")
    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(conn, record): conn.execute("PRAGMA foreign_keys=ON")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async def override():
        async with sessions() as db: yield db
    api_app.dependency_overrides[get_db] = override
    yield sessions
    api_app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(factory):
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        yield client
