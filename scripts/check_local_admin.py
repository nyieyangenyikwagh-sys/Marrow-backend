"""Verify admin setup and HTTP status codes using disposable SQLite storage.

This checks the local authentication flow, not a deployed PostgreSQL database.
Run with: python -m scripts.check_local_admin
"""
import asyncio
import os
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet


def main():
    with TemporaryDirectory(prefix="morrow-admin-check-") as directory:
        root = Path(directory)
        os.environ.update(
            DATABASE_URL=f"sqlite+aiosqlite:///{(root / 'bank.db').as_posix()}",
            LOCAL_SESSION_DB=str(root / "sessions.db"),
            SESSION_BACKEND="sqlite",
            ENVIRONMENT="development",
            SECRET_KEY=secrets.token_hex(32),
            ENCRYPTION_KEY=Fernet.generate_key().decode(),
        )

        from alembic import command
        from alembic.config import Config

        command.upgrade(Config("alembic.ini"), "head")

        from httpx import ASGITransport, AsyncClient
        from app.core.database import engine
        from app.core.redis import client as sessions
        from app.main import app
        from scripts.seed import seed

        async def verify():
            try:
                await seed("123456781234", reset_admin=True)
                # A normal repeated seed must not overwrite the admin password.
                await seed("DifferentPassword123!")
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
                    health = await client.get("/health")
                    assert health.status_code == 200, health.text
                    assert health.json() == {"status": "ok"}
                    print("GET /health: 200 OK; status=ok")

                    login = await client.post("/api/v1/auth/admin/login", json={
                        "email": "admin@morrow.local", "password": "123456781234",
                    })
                    assert login.status_code == 200, login.text
                    print("POST /api/v1/auth/admin/login: 200 OK")
                    tokens = login.json()

                    profile = await client.get("/api/v1/admin/me", headers={
                        "Authorization": f"Bearer {tokens['access_token']}",
                    })
                    assert profile.status_code == 200, profile.text
                    assert profile.json()["email"] == "admin@morrow.local"
                    assert profile.json()["role"] == "admin", profile.text
                    print("GET /api/v1/admin/me: 200 OK; role=admin")

                    payload = {"refresh_token": tokens["refresh_token"]}
                    assert (await client.post("/api/v1/auth/refresh", json=payload)).status_code == 200
                    assert (await client.post("/api/v1/auth/logout", json=payload)).status_code == 204
                    assert (await client.post("/api/v1/auth/refresh", json=payload)).status_code == 401
                    print("Refresh, logout and token revocation: passed")
            finally:
                await sessions.aclose()
                await engine.dispose()

        asyncio.run(verify())


if __name__ == "__main__":
    main()
