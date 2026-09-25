from app.models.customer import Customer
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.ledger import LedgerEntry
from app.models.card import Card
from app.models.kyc import KYCDocument
from app.models.aml import AMLCheck
from app.models.audit import AuditLog
from app.models.user import User

from sqlalchemy import CheckConstraint, event

for table in (LedgerEntry.__table__, Transaction.__table__):
    table.append_constraint(CheckConstraint("amount > 0", name=f"ck_{table.name}_positive_amount"))
Transaction.__table__.append_constraint(CheckConstraint("fee_amount >= 0", name="ck_nonnegative_fee"))
for model in (Account, Card):
    for field in ("daily_limit", "monthly_limit"):
        model.__table__.append_constraint(CheckConstraint(f"{field} IS NULL OR {field} > 0", name=f"ck_{model.__tablename__}_{field}"))
Account.__table__.append_constraint(CheckConstraint("transaction_limit IS NULL OR transaction_limit > 0", name="ck_transaction_limit"))


def immutable(mapper, connection, target):
    raise ValueError("Ledger entries and audit logs are immutable")


for model in (LedgerEntry, AuditLog):
    event.listen(model, "before_update", immutable)
    event.listen(model, "before_delete", immutable)
