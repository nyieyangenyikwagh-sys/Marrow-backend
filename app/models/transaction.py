from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import TransactionType, TransactionStatus

class Transaction(Base):
    """The customer-facing 'request' record — see §1.2. Its `status`
    field is the only thing ever mutated after creation; everything else
    is fixed at insert time (a correction is a NEW transaction, §1.3)."""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    from_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    from_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    to_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    to_customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)

    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    currency_code = Column(String(3), nullable=False)

    to_currency_code = Column(String(3), nullable=True)
    exchange_rate = Column(Numeric(20, 8), nullable=True)
    converted_amount = Column(Numeric(20, 2), nullable=True)

    fee_amount = Column(Numeric(20, 2), default=0)
    description = Column(String(200), nullable=False, default="Transfer")
    fee_reason = Column(String(255), nullable=True)

    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING)

    reverses_transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True, unique=True)

    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)

    reference_number = Column(String(50), unique=True, nullable=True, index=True)
    merchant_name = Column(String(255), nullable=True)
    merchant_category = Column(String(50), nullable=True)

    transaction_date = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_from_account_id', 'from_account_id'),
        Index('idx_to_account_id', 'to_account_id'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )

    ledger_entries = relationship("LedgerEntry", back_populates="transaction")
