"""Explicit demo seed. Never runs automatically on application startup."""
import argparse
import asyncio
import getpass
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.config import settings
from app.core.constants import AccountType, KYCStatus, UserRole, TransactionType, TransactionStatus, EntryType
from app.models import Customer, Account, User, Transaction
from app.services.ledger_service import LedgerService
from app.services.audit_service import AuditService

CURRENCIES = ("USD", "CAD", "GBP", "EUR")


ADMIN_EMAIL = "admin@morrow.local"


async def seed(password, demo=False, reset_admin=False):
    if len(password) < 12:
        raise ValueError("Password must have at least 12 characters")
    if demo and settings.ENVIRONMENT == "production":
        raise ValueError("Demo funding is disabled in production")
    async with AsyncSessionLocal() as db:
        internal = await db.scalar(select(Customer).where(Customer.email == "system@koho.internal"))
        if not internal:
            internal = Customer(email="system@koho.internal", password_hash=hash_password(secrets.token_urlsafe(48)),
                                first_name="Bank", last_name="System", kyc_status=KYCStatus.VERIFIED)
            db.add(internal)
            await db.flush()
        for currency in CURRENCIES:
            for name in ("SYSTEM-FEE-REVENUE", "SYSTEM-CLEARING"):
                number = f"{name}-{currency}"
                if not await db.scalar(select(Account.id).where(Account.account_number == number)):
                    db.add(Account(customer_id=internal.id, account_name=name, account_number=number,
                                   account_type=AccountType.CHECKING, currency_code=currency, is_internal=True))
        admin = await db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if not admin:
            # Preserve the old seed administrator's identity when explicitly resetting.
            if reset_admin:
                admin = await db.scalar(select(User).where(User.email == "admin@koho.local"))
            if not admin:
                admin = User(email=ADMIN_EMAIL, password_hash=hash_password(password),
                             first_name="Morrow", last_name="Admin", role=UserRole.ADMIN)
                db.add(admin)
        if reset_admin:
            admin.email = ADMIN_EMAIL
            admin.password_hash = hash_password(password)
            admin.role = UserRole.ADMIN
            admin.is_active = True
        if demo:
            for email, first, last in (("alex@example.com", "Alex", "Morgan"), ("sam@example.com", "Sam", "Chen")):
                customer = await db.scalar(select(Customer).where(Customer.email == email))
                if customer:
                    continue
                customer = Customer(email=email, first_name=first, last_name=last,
                    password_hash=hash_password(password), kyc_status=KYCStatus.VERIFIED, country="CA",
                    kyc_verified_at=datetime.now(timezone.utc))
                db.add(customer)
                await db.flush()
                for kind, amount in ((AccountType.CHECKING, Decimal("12500.00")), (AccountType.SAVINGS, Decimal("8200.00"))):
                    account = Account(customer_id=customer.id, account_name="Everyday spending" if kind == AccountType.CHECKING else "Rainy day savings",
                        account_number=f"{kind.value[:3].upper()}-{secrets.randbelow(10**10):010d}",
                        account_type=kind, currency_code="CAD", is_primary=kind == AccountType.CHECKING,
                        daily_limit=Decimal("25000"), monthly_limit=Decimal("100000"), transaction_limit=Decimal("20000"))
                    db.add(account)
                    await db.flush()
                    clearing = await db.scalar(select(Account).where(Account.account_number == "SYSTEM-CLEARING-CAD"))
                    now = datetime.now(timezone.utc)
                    txn = Transaction(from_customer_id=internal.id, from_account_id=clearing.id,
                        to_customer_id=customer.id, to_account_id=account.id, transaction_type=TransactionType.DEPOSIT,
                        amount=amount, fee_amount=Decimal("0"), currency_code="CAD", status=TransactionStatus.COMPLETED,
                        idempotency_key=f"demo-opening-{account.id}", description="Demo opening funds",
                        reference_number=f"DEMO-{secrets.token_hex(8).upper()}", transaction_date=now, completed_at=now)
                    db.add(txn)
                    await db.flush()
                    for a, direction in ((clearing, EntryType.DEBIT), (account, EntryType.CREDIT)):
                        await LedgerService.create_entry(db, txn.id, a.id, a.customer_id, direction,
                                                         amount, "CAD", "Demo opening funds")
                    await AuditService.log_action(db, entity_type="transaction", entity_id=txn.id, action="demo_funding")
        await db.commit()
    print(f"Seed complete. Staff: {ADMIN_EMAIL}" + ("; customers: alex@example.com, sam@example.com" if demo else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--reset-admin", action="store_true", help="Reset the seed admin password, role and active status")
    parser.add_argument("--local-admin", action="store_true", help="Use the requested local development admin password")
    args = parser.parse_args()
    if args.local_admin and settings.ENVIRONMENT != "development":
        parser.error("--local-admin is only supported in development")
    password = "123456781234" if args.local_admin else getpass.getpass("Set seed password (minimum 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must have at least 12 characters")
    asyncio.run(seed(password, args.demo, reset_admin=args.reset_admin))
