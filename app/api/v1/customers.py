from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.core.constants import UserRole, CustomerStatus
from app.models.customer import Customer
from app.services.customer_service import CustomerService
from app.schemas.customer import CustomerResponse, CustomerAdminResponse, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["customers"])

@router.get("/me", response_model=CustomerResponse)
async def get_my_profile(current_user: Customer = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=CustomerResponse)
async def update_my_profile(
    data: CustomerUpdate,
    current_user: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer = await CustomerService.update_profile(db, current_user.id, data)
        await db.commit()
        return customer
    except ValueError as e:
        await db.rollback()
        raise HTTPException(404, str(e))

@router.get("", response_model=list[CustomerAdminResponse])
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    kyc_status: Optional[str] = None,
    customer_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE, UserRole.SUPPORT)),
):
    """Any staff role can VIEW the list — viewing isn't the sensitive
    action here; freezing/unfreezing (below) is, and is scoped tighter."""
    customers, _total = await CustomerService.list_customers(
        db, page, page_size, kyc_status, customer_status
    )
    return customers

@router.get("/{customer_id}", response_model=CustomerAdminResponse)
async def get_customer_admin_view(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    _staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE, UserRole.SUPPORT)),
):
    customer = await CustomerService.get_by_id(db, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    return customer

@router.post("/{customer_id}/freeze", response_model=CustomerAdminResponse)
async def freeze_customer(
    customer_id: UUID,
    reason: str,
    db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        customer = await CustomerService.set_status(
            db, customer_id, CustomerStatus.FROZEN, staff.id, reason
        )
        await db.commit()
        return customer
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))

@router.post("/{customer_id}/unfreeze", response_model=CustomerAdminResponse)
async def unfreeze_customer(
    customer_id: UUID,
    reason: str,
    db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        customer = await CustomerService.set_status(
            db, customer_id, CustomerStatus.ACTIVE, staff.id, reason
        )
        await db.commit()
        return customer
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
