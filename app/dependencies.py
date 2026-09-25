from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import JWTError
from uuid import UUID

from app.core.database import get_db
from app.core.security import decode_token
from app.core.redis import get_redis  # new — see §10.6
from app.models.customer import Customer
from app.models.user import User
from app.core.constants import CustomerStatus, UserRole

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    """Resolve the calling Customer from a Bearer access token. All JWT
    decode/validate logic now lives in security.py (Section 7) — this
    function's only job is translating that into HTTP semantics and
    loading the actual row."""
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if payload.get("type") != "customer" or payload.get("sub") is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    customer = await db.get(Customer, UUID(payload["sub"]))
    if customer is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Customer not found")
    if customer.customer_status != CustomerStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is not active")

    return customer

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if payload.get("type") != "admin" or payload.get("sub") is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin access required")

    admin = await db.get(User, UUID(payload["sub"]))
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")

    return admin

def require_role(*allowed_roles: UserRole):
    """Dependency factory — added in Section 11 after finding that
    get_current_admin (above) only ever admits UserRole.ADMIN, despite
    the source docs USING get_current_admin to gate KYC verification and
    AML review (Section 15-16) — tasks the User model's own UserRole
    enum says COMPLIANCE staff should be able to do. As shipped, a
    compliance officer with a valid, active account could never pass
    get_current_admin at all; the role field existed but nothing ever
    branched on it beyond the single hardcoded "admin" check.

    Usage: Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE))
    get_current_admin is kept as-is for endpoints that should genuinely
    be ADMIN-only (e.g. Section 19's admin-dashboard config changes);
    require_role is used everywhere the source docs used get_current_admin
    for what was actually a compliance or support task.
    """
    async def _check(admin: User = Depends(get_current_admin)) -> User:
        if admin.role not in allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of: {', '.join(r.value for r in allowed_roles)}",
            )
        return admin
    return _check
