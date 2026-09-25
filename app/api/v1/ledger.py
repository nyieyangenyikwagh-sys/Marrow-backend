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


@router.get("/{account_id}/statement-csv")
async def statement_csv(account_id: UUID, start: datetime, end: datetime,
                         db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    import csv
    import io
    from fastapi.responses import Response
    from app.core.constants import EntryType
    account = await owned(db, account_id, user)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Statement dates must include a timezone")
    statement = await LedgerService.get_statement(db, account_id, start, end)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Reference", "Description", "Debit", "Credit", "Balance", "Currency"])
    balance = statement["opening_balance"]
    writer.writerow([start.isoformat(), "", "Opening balance", "", "", str(balance), account.currency_code])
    def safe(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
    for entry in statement["entries"]:
        credit = entry.entry_type == EntryType.CREDIT
        balance += entry.amount if credit else -entry.amount
        writer.writerow([entry.entry_date.isoformat(), safe(entry.reference_number), safe(entry.description),
                         "" if credit else str(entry.amount), str(entry.amount) if credit else "", str(balance), account.currency_code])
    writer.writerow([end.isoformat(), "", "Closing balance", "", "", str(balance), account.currency_code])
    return Response(output.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="statement-{account_id}.csv"'})


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
