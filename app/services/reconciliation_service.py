"""Read-only accounting checks; callers provide a consistent database snapshot."""
from sqlalchemy import select, func, case, or_
from app.models import Account, Transaction, LedgerEntry
from app.core.constants import EntryType, TransactionStatus


async def reconcile(db):
    debit = case((LedgerEntry.entry_type == EntryType.DEBIT, LedgerEntry.amount), else_=0)
    credit = case((LedgerEntry.entry_type == EntryType.CREDIT, LedgerEntry.amount), else_=0)
    currency_rows = (await db.execute(select(LedgerEntry.currency_code, func.sum(debit), func.sum(credit))
                                      .group_by(LedgerEntry.currency_code))).all()
    unbalanced = (await db.execute(select(LedgerEntry.transaction_id, LedgerEntry.currency_code)
        .group_by(LedgerEntry.transaction_id, LedgerEntry.currency_code)
        .having(or_(func.sum(debit) != func.sum(credit), func.count() < 2)))).all()
    counts = select(LedgerEntry.transaction_id.label("id"), func.count().label("legs")).group_by(LedgerEntry.transaction_id).subquery()
    invalid_states = (await db.scalars(select(Transaction.id).outerjoin(counts, Transaction.id == counts.c.id).where(or_(
        Transaction.status.in_([TransactionStatus.COMPLETED, TransactionStatus.REVERSED]) & (func.coalesce(counts.c.legs, 0) < 2),
        Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.FAILED]) & (func.coalesce(counts.c.legs, 0) > 0)
    )))).all()
    mismatches = (await db.scalars(select(LedgerEntry.id).join(Account, LedgerEntry.account_id == Account.id).where(or_(
        LedgerEntry.customer_id != Account.customer_id, LedgerEntry.currency_code != Account.currency_code)))).all()
    negative = (await db.execute(select(Account.id, func.sum(credit - debit)).join(LedgerEntry, LedgerEntry.account_id == Account.id)
        .where(Account.is_internal.is_(False)).group_by(Account.id).having(func.sum(credit - debit) < 0))).all()
    issues = {
        "unbalanced_transactions": [{"id": str(r[0]), "currency": r[1]} for r in unbalanced],
        "invalid_transaction_states": list(map(str, invalid_states)),
        "ownership_or_currency_mismatches": list(map(str, mismatches)),
        "negative_customer_accounts": [{"id": str(r[0]), "balance": str(r[1])} for r in negative],
    }
    return {"ok": not any(issues.values()) and all(r[1] == r[2] for r in currency_rows),
            "currencies": [{"currency": r[0], "debits": str(r[1]), "credits": str(r[2])} for r in currency_rows],
            "issues": issues}
