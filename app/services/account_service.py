from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
import secrets

from app.models.account import Account
from app.core.constants import AccountType, AccountStatus
from app.schemas.account import AccountCreate
from app.services.audit_service import AuditService
from app.models.customer import Customer
from app.core.constants import KYCStatus, CustomerStatus, TransactionStatus
from app.models.transaction import Transaction
from app.services.ledger_service import LedgerService
from sqlalchemy import or_

def _generate_account_number(account_type: AccountType) -> str:
    prefix = {AccountType.CHECKING: "CHK", AccountType.SAVINGS: "SAV", AccountType.CREDIT: "CRD"}[account_type]
    digits = "".join(secrets.choice("0123456789") for _ in range(10))
    return f"{prefix}-{digits}"

class AccountService:

    @staticmethod
    async def create_account(
        db: AsyncSession, customer_id: UUID, data: AccountCreate
    ) -> Account:
        customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
        if not customer or customer.kyc_status != KYCStatus.VERIFIED or customer.customer_status != CustomerStatus.ACTIVE:
            raise PermissionError("Active, verified customer required")
        for _ in range(5):
            account = Account(
                customer_id=customer_id,
                account_name=data.account_name,
                account_number=_generate_account_number(data.account_type),
                account_type=data.account_type,
                currency_code=data.currency_code,
                daily_limit=data.daily_limit,
                monthly_limit=data.monthly_limit,
                transaction_limit=data.transaction_limit,
            )
            try:
                async with db.begin_nested():
                    db.add(account)
                    await db.flush()
                break
            except IntegrityError:
                continue
        else:
            raise RuntimeError("Could not generate a unique account number after 5 attempts")

        await AuditService.log_action(
            db=db, entity_type="account", entity_id=account.id, action="account_created",
            actor_id=customer_id, actor_type="customer",
            new_values={"account_type": data.account_type.value, "currency_code": data.currency_code},
        )
        return account

    @staticmethod
    async def get_account(db: AsyncSession, account_id: UUID) -> Optional[Account]:
        return await db.get(Account, account_id)

    @staticmethod
    async def list_customer_accounts(db: AsyncSession, customer_id: UUID) -> list[Account]:
        result = await db.execute(
            select(Account).where(
                Account.customer_id == customer_id,
                Account.is_internal.is_(False),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_limits(
        db: AsyncSession, account_id: UUID, admin_id: UUID,
        daily_limit=None, monthly_limit=None, transaction_limit=None, fields=None,
    ) -> Account:
        account = await LedgerService.lock_account_for_update(db, account_id)
        if not account:
            raise ValueError("Account not found")

        if account.is_internal or account.account_status == AccountStatus.CLOSED:
            raise ValueError("Only open customer accounts can have limits changed")

        old_values = {
            "daily_limit": account.daily_limit, "monthly_limit": account.monthly_limit,
            "transaction_limit": account.transaction_limit,
        }
        for value in (daily_limit, monthly_limit, transaction_limit):
            if value is not None and (not value.is_finite() or value <= 0):
                raise ValueError("Limits must be positive finite amounts")
        if daily_limit is not None or fields and "daily_limit" in fields:
            account.daily_limit = daily_limit
        if monthly_limit is not None or fields and "monthly_limit" in fields:
            account.monthly_limit = monthly_limit
        if transaction_limit is not None or fields and "transaction_limit" in fields:
            account.transaction_limit = transaction_limit

        await AuditService.log_action(
            db=db, entity_type="account", entity_id=account.id, action="limits_updated",
            actor_id=admin_id, actor_type="admin",
            old_values={k: str(v) if v else None for k, v in old_values.items()},
            new_values={field: str(getattr(account, field)) if getattr(account, field) is not None else None
                        for field in ("daily_limit", "monthly_limit", "transaction_limit")},
        )
        return account

    @staticmethod
    async def set_status(
        db: AsyncSession, account_id: UUID, new_status: AccountStatus,
        actor_id: UUID, actor_type: str, reason: str,
    ) -> Account:
        """Mirrors §11.1's CustomerService.set_status pattern deliberately
        — one method for both directions, same audit shape. Distinct from
        freezing a CUSTOMER (§11.1): this freezes one specific account,
        which is exactly why the two fields were renamed apart in §8.2."""
        account = await LedgerService.lock_account_for_update(db, account_id)
        if not account:
            raise ValueError("Account not found")
        if account.account_status == new_status:
            raise ValueError(f"Account is already {new_status.value}")
        if account.account_status == AccountStatus.CLOSED:
            raise ValueError("Closed accounts cannot be reopened")
        if account.is_internal:
            raise ValueError("Internal account status is managed by the system")
        if new_status == AccountStatus.CLOSED:
            if await LedgerService.get_account_balance(db, account_id) != 0:
                raise ValueError("Only zero-balance accounts can be closed")
            if await db.scalar(select(Transaction.id).where(
                or_(Transaction.from_account_id == account_id, Transaction.to_account_id == account_id),
                Transaction.status == TransactionStatus.PENDING).limit(1)):
                raise ValueError("Account has pending transactions")

        old_status = account.account_status
        account.account_status = new_status

        await AuditService.log_action(
            db=db, entity_type="account", entity_id=account.id,
            action=f"status_change_{new_status.value}",
            actor_id=actor_id, actor_type=actor_type,
            old_values={"account_status": old_status.value},
            new_values={"account_status": new_status.value, "reason": reason},
        )
        return account
