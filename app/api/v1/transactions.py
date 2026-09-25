from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from app.models.transaction import Transaction

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.core.constants import UserRole
from app.models.customer import Customer
from app.services.transfer_service import TransferService
from app.services.transaction_service import TransactionService
from app.schemas.transaction import TransferRequest, TransactionResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])

class ReviewRequest(BaseModel):
    notes: str = Field(min_length=3, max_length=500)

class ReverseRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=190)

@router.get("", response_model=list[TransactionResponse])
async def list_transactions(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                            db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return (await db.scalars(select(Transaction).where(or_(Transaction.from_customer_id == current_user.id,
        Transaction.to_customer_id == current_user.id)).order_by(Transaction.transaction_date.desc(), Transaction.id)
        .limit(limit).offset(offset))).all()

@router.post("/transfer", response_model=TransactionResponse, status_code=201)
async def transfer(
    request: TransferRequest,
    current_user: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.account_service import AccountService
    from_account = await AccountService.get_account(db, request.from_account_id)
    if not from_account or from_account.customer_id != current_user.id:
        raise HTTPException(403, "You do not own the source account")

    try:
        transaction = await TransferService.transfer(
            db=db, from_account_id=request.from_account_id, to_account_id=request.to_account_id,
            amount=request.amount, description=request.description,
            idempotency_key=request.idempotency_key,
        )
        await db.commit()
        await TransferService.cache_committed(transaction)
        return transaction
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
    except PermissionError as e:
        await db.rollback()
        raise HTTPException(403, str(e))
    except RuntimeError as e:
        await db.rollback()
        raise HTTPException(500, f"Ledger integrity check failed: {e}")

@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    current_user: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        transaction = await TransactionService.get_by_id(db, transaction_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    if current_user.id not in (transaction.from_customer_id, transaction.to_customer_id):
        raise HTTPException(404, "Transaction not found")   # 404, not 403 — don't confirm existence to a non-party
    return transaction

@router.post("/{transaction_id}/review/approve", response_model=TransactionResponse)
async def approve_review(
    transaction_id: UUID, data: ReviewRequest, db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        transaction = await TransactionService.review_approve(db, transaction_id, staff.id, data.notes)
        await db.commit()
        return transaction
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))

@router.post("/{transaction_id}/review/reject", response_model=TransactionResponse)
async def reject_review(
    transaction_id: UUID, data: ReviewRequest, db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        transaction = await TransactionService.review_reject(db, transaction_id, staff.id, data.notes)
        await db.commit()
        return transaction
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))

@router.post("/{transaction_id}/reverse", response_model=TransactionResponse)
async def reverse_transaction(
    transaction_id: UUID, data: ReverseRequest, db: AsyncSession = Depends(get_db),
    staff = Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE)),
):
    try:
        reversal = await TransactionService.reverse(db, transaction_id, staff.id, data.reason)
        await db.commit()
        return reversal
    except ValueError as e:
        await db.rollback()
        raise HTTPException(400, str(e))
