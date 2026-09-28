import pytest

from app.core.constants import UserRole
from app.core.security import hash_password
from app.models.user import User
from app.core.local_sessions import LocalSessions


@pytest.fixture
def local_sessions(tmp_path, monkeypatch):
    store = LocalSessions(tmp_path / "sessions.db")
    async def get():
        return store
    monkeypatch.setattr("app.main.client", store)
    monkeypatch.setattr("app.services.auth_service.get_redis", get)
    return store


async def test_seeded_local_staff_login(client, factory, local_sessions):
    password = "LocalStaffPassword123!"
    async with factory() as db:
        db.add(User(email="admin@koho.local", password_hash=hash_password(password),
                    first_name="Alex", last_name="Morgan", role=UserRole.ADMIN))
        await db.commit()

    response = await client.post("/api/v1/auth/admin/login", json={
        "email": " ADMIN@KOHO.LOCAL ", "password": password,
    })
    assert response.status_code == 200, response.text
    tokens = response.json()
    assert tokens["refresh_token"]
    profile = await client.get("/api/v1/admin/me", headers={
        "Authorization": f"Bearer {tokens['access_token']}",
    })
    assert profile.status_code == 200, profile.text
    assert profile.json()["email"] == "admin@koho.local"

    denied = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin@koho.local", "password": "incorrect-password",
    })
    assert denied.status_code == 401

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    logout = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 204
    revoked = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert revoked.status_code == 401


async def test_local_rate_limit(client, local_sessions):
    for _ in range(30):
        response = await client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422
    response = await client.post("/api/v1/auth/login", json={})
    assert response.status_code == 429


async def test_local_sessions_persist_and_expire(tmp_path, monkeypatch):
    import asyncio
    now = 1000.0
    monkeypatch.setattr("app.core.local_sessions.time.time", lambda: now)
    store = LocalSessions(tmp_path / "sessions.db")
    await store.set("revoked:test", "1", ex=120)
    restarted = LocalSessions(store.path)
    assert await restarted.exists("revoked:test")
    counts = await asyncio.gather(*(restarted.eval("", 1, "auth-rate:test") for _ in range(35)))
    assert sorted(counts) == list(range(1, 36))
    now += 61
    assert await restarted.eval("", 1, "auth-rate:test") == 1
    assert await restarted.exists("revoked:test")
    now += 60
    assert not await restarted.exists("revoked:test")


async def test_redis_failure_still_fails_closed(client, monkeypatch):
    from redis.exceptions import ConnectionError
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.main.client.eval", AsyncMock(side_effect=ConnectionError("offline")))
    response = await client.post("/api/v1/auth/login", json={})
    assert response.status_code == 503


def test_production_rejects_local_sessions():
    from app.core.config import Settings, settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="only supported in development"):
        Settings(**{**settings.model_dump(), "ENVIRONMENT": "production",
                    "DATABASE_URL": "postgresql://localhost/test", "SESSION_BACKEND": "sqlite"})


@pytest.mark.parametrize("email", ["", "   ", "a" * 256, None])
async def test_login_rejects_invalid_identifier(client, email):
    response = await client.post("/api/v1/auth/admin/login", json={
        "email": email, "password": "LocalStaffPassword123!",
    })
    assert response.status_code == 422


async def test_signup_still_rejects_reserved_email(client):
    response = await client.post("/api/v1/auth/signup", json={
        "email": "new@koho.local", "password": "LocalStaffPassword123!",
        "first_name": "New", "last_name": "Customer",
    })
    assert response.status_code == 422
