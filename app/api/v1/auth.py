from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.services.auth_service import AuthService
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(data: CustomerCreate, db: AsyncSession = Depends(get_db)):
    try:
        from app.models.customer import Customer
        customer, access, refresh = await AuthService.signup(db, data)
        await db.commit()
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        _, access, refresh = await AuthService.login(db, data.email, data.password)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(401, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))

@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        new_access = await AuthService.refresh_access_token(db, data.refresh_token)
        return TokenResponse(access_token=new_access, refresh_token=data.refresh_token)
    except ValueError as e:
        raise HTTPException(401, str(e))

@router.post("/logout", status_code=204)
async def logout(data: RefreshRequest):
    await AuthService.logout(data.refresh_token)

@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        _, access, refresh = await AuthService.admin_login(db, data.email, data.password)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(401, str(e))
