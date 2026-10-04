"""Check seeded logins and sessions against configured, real storage."""
import asyncio
import getpass

from httpx import ASGITransport, AsyncClient
from app.main import app


async def check_login(password):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        health = await client.get("/health")
        assert health.status_code == 200, "Database or session store unavailable"
        for email, route, profile in (
            ("admin@morrow.local", "admin/login", "/api/v1/admin/me"),
            ("alex@example.com", "login", "/api/v1/customers/me"),
        ):
            response = await client.post(f"/api/v1/auth/{route}", json={"email": email, "password": password})
            assert response.status_code == 200, f"{email}: {response.status_code} {response.text}"
            tokens = response.json()
            response = await client.get(profile, headers={"Authorization": f"Bearer {tokens['access_token']}"})
            assert response.status_code == 200, f"Profile failed for {email}"
            payload = {"refresh_token": tokens["refresh_token"]}
            assert (await client.post("/api/v1/auth/refresh", json=payload)).status_code == 200
            assert (await client.post("/api/v1/auth/logout", json=payload)).status_code == 204
            assert (await client.post("/api/v1/auth/refresh", json=payload)).status_code == 401
            print(f"Verified {email}: login, profile, refresh, logout, revocation")


if __name__ == "__main__":
    asyncio.run(check_login(getpass.getpass("Seed account password: ")))
