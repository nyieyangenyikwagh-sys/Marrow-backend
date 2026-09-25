import hashlib
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime, timezone
from uuid import uuid4, UUID
from redis.exceptions import RedisError
from app.core.redis import get_redis
from sqlalchemy import select, func, text
from app.models.transaction import Transaction
from app.models.account import Account
from app.models.customer import Customer
from app.services.ledger_service import LedgerService
from app.services.aml_service import AMLService
from app.services.audit_service import AuditService
from app.core.constants import (EntryType, TransactionType, TransactionStatus, AccountStatus,
                                CustomerStatus, KYCStatus, AMLResolution)
from app.core.config import settings

INTERNAL_FEE_REVENUE_ACCOUNT_NUMBER = "SYSTEM-FEE-REVENUE"


class TransferService:
    @staticmethod
    async def lock_accounts(db, ids):
        return {i: await LedgerService.lock_account_for_update(db, i) for i in sorted(set(ids))}

    @staticmethod
    async def validate_accounts(db, source, destination, amount, fee, exclude_transaction=None):
        if source.id == destination.id:
            raise ValueError("Source and destination must differ")
        if source.is_internal or destination.is_internal:
            raise PermissionError("Internal accounts cannot be used for customer transfers")
        if source.account_status != AccountStatus.ACTIVE or destination.account_status != AccountStatus.ACTIVE:
            raise PermissionError("Both accounts must be active")
        if source.currency_code != destination.currency_code:
            raise ValueError("Cross-currency transfers are not supported")
        # Lock customer rows as well so a freeze cannot race the posting decision.
        for customer_id in sorted({source.customer_id, destination.customer_id}):
            customer = await db.scalar(select(Customer).where(Customer.id == customer_id)
                                       .with_for_update().execution_options(populate_existing=True))
            if customer.customer_status != CustomerStatus.ACTIVE:
                raise PermissionError("Customer is not active")
            if customer.kyc_status != KYCStatus.VERIFIED:
                raise PermissionError("KYC verification required for both parties")
        debit = amount + fee
        if source.transaction_limit is not None and debit > source.transaction_limit:
            raise ValueError("Transaction limit exceeded (including fees)")
        now = datetime.now(timezone.utc)
        for field, start in (("daily_limit", now.replace(hour=0, minute=0, second=0, microsecond=0)),
                             ("monthly_limit", now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))):
            limit = getattr(source, field)
            if limit is None:
                continue
            query = select(func.coalesce(func.sum(Transaction.amount + Transaction.fee_amount), 0)).where(
                Transaction.from_account_id == source.id,
                Transaction.transaction_type == TransactionType.TRANSFER,
                Transaction.status.in_([TransactionStatus.COMPLETED, TransactionStatus.REVERSED]),
                Transaction.completed_at >= start)
            if exclude_transaction:
                query = query.where(Transaction.id != exclude_transaction)
            if (await db.scalar(query)) + debit > limit:
                raise ValueError(f"{field.replace('_', ' ').capitalize()} exceeded (including fees)")
        if await LedgerService.get_account_balance(db, source.id) < debit:
            raise ValueError("Insufficient funds (including fees)")

    @staticmethod
    async def transfer(db, from_account_id, to_account_id, amount, description="Transfer", idempotency_key=None):
        if not idempotency_key:
            raise ValueError("An idempotency key is required")
        if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Amount must have at most two decimal places")
        if not settings.MIN_TRANSFER_AMOUNT <= amount <= settings.MAX_TRANSFER_AMOUNT:
            raise ValueError("Amount is outside transfer limits")
        # Serialize the same request before any reads. The unique constraint remains the final guard.
        scoped_key = f"{from_account_id}:{idempotency_key}"
        if db.bind.dialect.name == "postgresql":
            lock_id = int.from_bytes(hashlib.sha256(scoped_key.encode()).digest()[:8], "big", signed=True)
            await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
        existing = None
        cache_key = 'idempotency:' + hashlib.sha256(scoped_key.encode()).hexdigest()
        try:
            cached_id = await (await get_redis()).get(cache_key)
            if cached_id:
                existing = await db.get(Transaction, UUID(cached_id), populate_existing=True)
                if existing and existing.idempotency_key != scoped_key:
                    existing = None
        except (RedisError, ValueError):
            pass  # PostgreSQL remains authoritative when the optional cache is unavailable.
        if existing is None:
            existing = await db.scalar(select(Transaction).where(Transaction.idempotency_key == scoped_key))
        if existing:
            if (existing.from_account_id, existing.to_account_id, existing.amount, existing.description) != (
                    from_account_id, to_account_id, amount, description):
                raise ValueError("Idempotency key was already used with different request data")
            return existing
        accounts = await TransferService.lock_accounts(db, [from_account_id, to_account_id])
        source, destination = accounts[from_account_id], accounts[to_account_id]
        fee = (amount * settings.TRANSFER_FEE_PERCENTAGE).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        await TransferService.validate_accounts(db, source, destination, amount, fee)
        check = await AMLService.check_transaction(db, source.customer_id, amount, TransactionType.TRANSFER)
        status = {AMLResolution.APPROVED: TransactionStatus.COMPLETED,
                  AMLResolution.REVIEW: TransactionStatus.PENDING,
                  AMLResolution.BLOCKED: TransactionStatus.FAILED}[check.resolution]
        now = datetime.now(timezone.utc)
        transaction = Transaction(from_customer_id=source.customer_id, from_account_id=source.id,
            to_customer_id=destination.customer_id, to_account_id=destination.id,
            transaction_type=TransactionType.TRANSFER, amount=amount, currency_code=source.currency_code,
            fee_amount=fee, fee_reason="Transfer fee", description=description, status=status,
            idempotency_key=scoped_key, reference_number=f"TXN-{uuid4().hex[:16].upper()}",
            transaction_date=now, completed_at=now if status == TransactionStatus.COMPLETED else None)
        db.add(transaction)
        await db.flush()
        check.transaction_id = transaction.id
        if status == TransactionStatus.COMPLETED:
            await TransferService.post(db, transaction, source, destination)
        await AuditService.log_action(db, entity_type="transaction", entity_id=transaction.id,
            action="transfer_requested", actor_id=source.customer_id, actor_type="customer",
            new_values={"status": status.value, "amount": str(amount)})
        return transaction

    @staticmethod
    async def cache_committed(transaction):
        key = 'idempotency:' + hashlib.sha256(transaction.idempotency_key.encode()).hexdigest()
        try:
            await (await get_redis()).set(key, str(transaction.id), ex=86400)
        except RedisError:
            pass

    @staticmethod
    async def post(db, transaction, source, destination):
        fee_account = await db.scalar(select(Account).where(Account.is_internal.is_(True),
            Account.account_number == f"{INTERNAL_FEE_REVENUE_ACCOUNT_NUMBER}-{source.currency_code}"))
        if transaction.fee_amount and not fee_account:
            raise ValueError("Fee account is not configured for this currency")
        await TransferService._post_transfer_legs(db, transaction, source, destination, fee_account, transaction.description)
        if not await LedgerService.verify_ledger_integrity(db, transaction.id):
            raise RuntimeError("Ledger integrity check failed")

    @staticmethod
    async def _post_transfer_legs(db, transaction, source, destination, fee_account, description):
        legs = [(source, EntryType.DEBIT, transaction.amount), (destination, EntryType.CREDIT, transaction.amount)]
        if transaction.fee_amount:
            legs += [(source, EntryType.DEBIT, transaction.fee_amount),
                     (fee_account, EntryType.CREDIT, transaction.fee_amount)]
        for account, direction, amount in legs:
            await LedgerService.create_entry(db, transaction.id, account.id, account.customer_id,
                direction, amount, account.currency_code, description,
                reference_number=transaction.reference_number)
