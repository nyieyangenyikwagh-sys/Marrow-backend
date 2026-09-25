from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.core.constants import UserRole, AccountStatus
from app.models.customer import Customer
from app.services.account_service import AccountService
from app.schemas.account import AccountCreate, AccountResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])

class LimitsUpdateRequest(BaseModel):
    daily_limit: Optional[Decimal] = Field(None, gt=0, max_digits=20, decimal_places=2)
    monthly_limit: Optional[Decimal] = Field(None, gt=0, max_digits=20, decimal_places=2)
    transaction_limit: Optional[Decimal] = Field(None, gt=0, max_digits=20, decimal_places=2)

class StatusChangeRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

@router.post("/{account_id}/unfreeze", response_model=AccountResponse)
async def unfreeze_account(account_id: UUID, data: StatusChangeRequest, db: AsyncSession = Depends(get_db),
                           staff=Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE))):
    account = await AccountService.set_status(db, account_id, AccountStatus.ACTIVE, staff.id, "admin", data.reason)
    await db.commit()
    return account

@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    data: AccountCreate,
    current_user: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.kyc_status.value != "verified":
        raise HTTPException(403, "KYC verification required before opening an account")

    account = await AccountService.create_account(db, current_user.id, data)
    await db.commit()
    return account

@router.get("/me", response_model=list[AccountResponse])
async def list_my_accounts(
    current_user: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AccountService.list_customer_accounts(db, current_user.id)

@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    current_user: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await AccountService.get_account(db, account_id)
    if not account or account.is_internal:
        raise HTTPException(404, "Account not found")
    if account.customer_id != current_user.id:
        raise HTTPException(404, "Account not found")
    return account

@router.patch("/{account_id}/limits", response_model=AccountResponse)
async def update_account_limits(
    account_id: UUID,
    data: LimitsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        account = await AccountService.update_limits(
            db, account_id, staff.id,
            data.daily_limit, data.monthly_limit, data.transaction_limit,
            fields=data.model_fields_set,
        )
        await db.commit()
        return account
    except ValueError as e:
        await db.rollback()
        raise HTTPException(404, str(e))

@router.post("/{account_id}/freeze", response_model=AccountResponse)
async def freeze_account(
    account_id: UUID,
    data: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        account = await AccountService.set_status(
            db, account_id, AccountStatus.FROZEN, staff.id, "admin", data.reason
        )
        await db.commit()
        return account
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))

@router.post("/{account_id}/close", response_model=AccountResponse)
async def close_account(
    account_id: UUID,
    data: StatusChangeRequest,
    db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        account = await AccountService.set_status(
            db, account_id, AccountStatus.CLOSED, staff.id, "admin", data.reason
        )
        await db.commit()
        return account
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
