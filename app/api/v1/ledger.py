from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.account import Account
from app.services.ledger_service import LedgerService
from app.schemas.ledger import BalanceResponse, LedgerEntryResponse, StatementResponse

router = APIRouter(prefix="/ledger", tags=["ledger"])


async def owned(db, account_id, user):
    account = await db.get(Account, account_id)
    if not account or account.customer_id != user.id or account.is_internal:
        raise HTTPException(404, "Account not found")
    return account


@router.get("/{account_id}/balance", response_model=BalanceResponse)
async def balance(account_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    account = await owned(db, account_id, user)
    return dict(account_id=account_id, balance=await LedgerService.get_account_balance(db, account_id),
                currency_code=account.currency_code, as_of=datetime.now(timezone.utc))


@router.get("/{account_id}/entries", response_model=list[LedgerEntryResponse])
async def entries(account_id: UUID, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                  db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await owned(db, account_id, user)
    rows, _ = await LedgerService.get_ledger_entries(db, account_id, limit, offset)
    return rows


@router.get("/{account_id}/statement", response_model=StatementResponse)
async def statement(account_id: UUID, start: datetime, end: datetime,
                    db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await owned(db, account_id, user)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Statement dates must include a timezone")
    return await LedgerService.get_statement(db, account_id, start, end)
