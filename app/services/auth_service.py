import time
from uuid import UUID
from sqlalchemy import select
from app.core.security import (hash_password, verify_password, create_access_token,
                               create_refresh_token, decode_token, JWTError, DUMMY_HASH)
from app.core.redis import get_redis
from app.models.customer import Customer
from app.models.user import User
from app.core.constants import CustomerStatus
from app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    def tokens(subject, kind):
        return create_access_token(subject, kind), create_refresh_token(subject, kind)

    @staticmethod
    async def signup(db, data):
        email = str(data.email).lower()
        if await db.scalar(select(Customer.id).where(Customer.email == email)):
            raise ValueError("An account with this email already exists")
        customer = Customer(**data.model_dump(exclude={"password", "email"}), email=email,
                            password_hash=hash_password(data.password))
        db.add(customer)
        await db.flush()
        await AuditService.log_action(db, entity_type="customer", entity_id=customer.id,
                                      action="signup", actor_id=customer.id, actor_type="customer")
        return customer, *AuthService.tokens(customer.id, "customer")

    @staticmethod
    async def _login(db, email, password, kind):
        model = User if kind == "admin" else Customer
        person = await db.scalar(select(model).where(model.email == str(email).lower()))
        valid = verify_password(password, person.password_hash if person else DUMMY_HASH)
        if not person or not valid:
            raise ValueError("Invalid email or password")
        active = person.is_active if kind == "admin" else person.customer_status == CustomerStatus.ACTIVE
        if not active:
            raise PermissionError("Account is not active")
        return person, *AuthService.tokens(person.id, kind)

    @staticmethod
    async def login(db, email, password):
        return await AuthService._login(db, email, password, "customer")

    @staticmethod
    async def admin_login(db, email, password):
        return await AuthService._login(db, email, password, "admin")

    @staticmethod
    async def refresh_access_token(db, refresh_token):
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise ValueError("Invalid or expired refresh token")
        if payload["type"] != "refresh":
            raise ValueError("Not a refresh token")
        redis = await get_redis()
        if await redis.exists(f"revoked:{payload['jti']}"):
            raise ValueError("This refresh token has been revoked")
        kind = payload["user_type"]
        person = await db.get(User if kind == "admin" else Customer, UUID(payload["sub"]))
        if not person or not (person.is_active if kind == "admin" else person.customer_status == CustomerStatus.ACTIVE):
            raise ValueError("Account is not active")
        return create_access_token(person.id, kind)

    @staticmethod
    async def logout(refresh_token):
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            return
        if payload["type"] != "refresh":
            raise ValueError("Not a refresh token")
        ttl = max(int(payload["exp"] - time.time()), 0)
        if ttl:
            await (await get_redis()).set(f"revoked:{payload['jti']}", "1", ex=ttl)
