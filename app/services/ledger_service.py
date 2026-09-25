from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, func, case
from app.models.ledger import LedgerEntry
from app.models.account import Account
from app.models.transaction import Transaction
from app.core.constants import EntryType, LedgerEntryStatus, TransactionStatus, TransactionType


class LedgerService:
    """Only this service writes ledger entries. Its caller owns the atomic commit."""
    @staticmethod
    async def lock_account_for_update(db, account_id):
        # NO KEY UPDATE still serializes balance decisions, while allowing the
        # FK key-share locks taken by ledger credits to internal fee accounts.
        # This prevents a fee credit and a reversal from creating a lock cycle.
        account = await db.scalar(select(Account).where(Account.id == account_id)
            .with_for_update(key_share=True).execution_options(populate_existing=True))
        if not account:
            raise ValueError("Account not found")
        return account

    @staticmethod
    async def create_entry(db, transaction_id, account_id, customer_id, entry_type, amount,
                           currency_code, description, reference_number=None,
                           source_account_id=None, destination_account_id=None, entry_date=None):
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Ledger amounts must be positive whole cents")
        account = await db.get(Account, account_id)
        if not account or account.customer_id != customer_id or account.currency_code != currency_code:
            raise ValueError("Ledger account, customer and currency must match")
        entry = LedgerEntry(transaction_id=transaction_id, account_id=account_id, customer_id=customer_id,
            entry_type=entry_type, amount=amount, currency_code=currency_code, description=description,
            reference_number=reference_number, source_account_id=source_account_id,
            destination_account_id=destination_account_id, entry_date=entry_date or datetime.now(timezone.utc),
            status=LedgerEntryStatus.COMPLETED)
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def get_account_balance(db, account_id, as_of_date=None, exclusive=False):
        query = select(func.coalesce(func.sum(case(
            (LedgerEntry.entry_type == EntryType.CREDIT, LedgerEntry.amount), else_=-LedgerEntry.amount)), 0)
        ).where(LedgerEntry.account_id == account_id)
        if as_of_date:
            query = query.where(LedgerEntry.entry_date < as_of_date if exclusive else LedgerEntry.entry_date <= as_of_date)
        return Decimal(await db.scalar(query))

    @staticmethod
    async def get_ledger_entries(db, account_id, limit=100, offset=0):
        query = select(LedgerEntry).where(LedgerEntry.account_id == account_id)
        entries = (await db.scalars(query.order_by(LedgerEntry.entry_date.desc(), LedgerEntry.id)
                                   .limit(limit).offset(offset))).all()
        count = await db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.account_id == account_id))
        return list(entries), count

    @staticmethod
    async def verify_ledger_integrity(db, transaction_id):
        rows = (await db.execute(select(
            func.sum(case((LedgerEntry.entry_type == EntryType.DEBIT, LedgerEntry.amount), else_=0)).label("debits"),
            func.sum(case((LedgerEntry.entry_type == EntryType.CREDIT, LedgerEntry.amount), else_=0)).label("credits")
        ).where(LedgerEntry.transaction_id == transaction_id).group_by(LedgerEntry.currency_code))).all()
        return bool(rows) and all(r.debits > 0 and r.debits == r.credits for r in rows)

    @staticmethod
    async def reverse_transaction(db, original_transaction_id, reason, actor_id):
        original = await db.scalar(select(Transaction).where(Transaction.id == original_transaction_id)
                                   .with_for_update().execution_options(populate_existing=True))
        if not original or original.status != TransactionStatus.COMPLETED:
            raise ValueError("Only completed transactions can be reversed")
        entries = (await db.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == original.id))).all()
        if not entries:
            raise ValueError("Transaction has no ledger entries")
        impacts = {}
        for entry in entries:
            impacts[entry.account_id] = impacts.get(entry.account_id, Decimal("0")) + (
                entry.amount if entry.entry_type == EntryType.DEBIT else -entry.amount)
        for account_id in sorted(impacts):
            account = await LedgerService.lock_account_for_update(db, account_id)
            if not account.is_internal and await LedgerService.get_account_balance(db, account_id) + impacts[account_id] < 0:
                raise ValueError("Reversal would overdraw a customer account")
        now = datetime.now(timezone.utc)
        reversal = Transaction(from_customer_id=original.from_customer_id, from_account_id=original.from_account_id,
            to_customer_id=original.to_customer_id, to_account_id=original.to_account_id,
            transaction_type=TransactionType.REVERSAL, amount=original.amount, fee_amount=original.fee_amount,
            currency_code=original.currency_code, status=TransactionStatus.COMPLETED, description=reason,
            reverses_transaction_id=original.id, idempotency_key=f"reversal-{original.id}",
            reference_number=f"REV-{uuid4().hex[:16].upper()}", transaction_date=now, completed_at=now)
        db.add(reversal)
        await db.flush()
        for entry in entries:
            await LedgerService.create_entry(db, reversal.id, entry.account_id, entry.customer_id,
                EntryType.DEBIT if entry.entry_type == EntryType.CREDIT else EntryType.CREDIT,
                entry.amount, entry.currency_code, f"Reversal: {reason}", reference_number=reversal.reference_number)
        if not await LedgerService.verify_ledger_integrity(db, reversal.id):
            raise RuntimeError("Reversal integrity check failed")
        original.status = TransactionStatus.REVERSED
        return reversal

    @staticmethod
    async def get_statement(db, account_id, start_date, end_date):
        if start_date > end_date:
            raise ValueError("End date must follow start date")
        entries = (await db.scalars(select(LedgerEntry).where(LedgerEntry.account_id == account_id,
            LedgerEntry.entry_date >= start_date, LedgerEntry.entry_date <= end_date)
            .order_by(LedgerEntry.entry_date, LedgerEntry.id))).all()
        opening = await LedgerService.get_account_balance(db, account_id, start_date, exclusive=True)
        closing = opening + sum((e.amount if e.entry_type == EntryType.CREDIT else -e.amount for e in entries), Decimal("0"))
        return dict(account_id=account_id, period_start=start_date, period_end=end_date,
                    opening_balance=opening, closing_balance=closing, entries=entries)
