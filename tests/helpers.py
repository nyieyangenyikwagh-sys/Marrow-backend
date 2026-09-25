from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from app.models import Customer, Account, Transaction, User
from app.core.constants import AccountType, KYCStatus, UserRole, TransactionStatus, TransactionType, EntryType
from app.core.security import hash_password, create_access_token
from app.services.ledger_service import LedgerService


async def funded(db, amount="25000.00"):
    people = [Customer(email=f"{uuid4()}@example.com", password_hash=hash_password("TestingPassword123!"),
                       first_name=name, last_name="Test", kyc_status=KYCStatus.VERIFIED) for name in ("Sender", "Receiver", "System")]
    db.add_all(people)
    await db.flush()
    source, dest, clearing, fees = [Account(customer_id=people[p].id, account_name=name, account_number=number,
        account_type=AccountType.CHECKING, currency_code="CAD", is_internal=internal)
        for p,name,number,internal in ((0,"Checking",f"CHK-{uuid4().hex[:10]}",False),
        (1,"Savings",f"SAV-{uuid4().hex[:10]}",False),(2,"Clearing",f"CLEAR-{uuid4().hex[:10]}",True),
        (2,"Fees","SYSTEM-FEE-REVENUE-CAD",True))]
    db.add_all([source,dest,clearing,fees])
    await db.flush()
    now = datetime.now(timezone.utc)
    txn = Transaction(from_customer_id=people[2].id, from_account_id=clearing.id,
        to_customer_id=people[0].id, to_account_id=source.id, amount=Decimal(amount), fee_amount=Decimal("0"),
        currency_code="CAD", transaction_type=TransactionType.DEPOSIT, status=TransactionStatus.COMPLETED,
        idempotency_key=str(uuid4()), transaction_date=now, completed_at=now)
    db.add(txn)
    await db.flush()
    for account, direction in ((clearing,EntryType.DEBIT),(source,EntryType.CREDIT)):
        await LedgerService.create_entry(db, txn.id, account.id, account.customer_id, direction, Decimal(amount), "CAD", "Funding")
    await db.commit()
    return source, dest, fees, people


def headers(person, kind="customer"):
    return {"Authorization": f"Bearer {create_access_token(person.id, kind)}"}
