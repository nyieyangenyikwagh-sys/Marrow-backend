import pytest

from app.core.constants import UserRole
from app.core.security import hash_password
from app.models.user import User


async def test_seeded_local_staff_login(client, factory):
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
