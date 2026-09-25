from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import EntryType, LedgerEntryStatus

class LedgerEntry(Base):
    """THE immutable core — see §1.1/§1.8. Never updated, never deleted,
    once written. Only LedgerService (Section 13) writes to this table."""
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)

    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)

    entry_type = Column(SQLEnum(EntryType), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    currency_code = Column(String(3), nullable=False)
    description = Column(String(255), nullable=False)

    source_account_id = Column(UUID(as_uuid=True), nullable=True)
    destination_account_id = Column(UUID(as_uuid=True), nullable=True)
    reference_number = Column(String(50), nullable=True)

    status = Column(SQLEnum(LedgerEntryStatus), default=LedgerEntryStatus.COMPLETED)

    entry_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index('idx_account_id_entry_date', 'account_id', 'entry_date'),
        Index('idx_transaction_id', 'transaction_id'),
        Index('idx_customer_id', 'customer_id'),
    )

    transaction = relationship("Transaction", back_populates="ledger_entries")

    def __repr__(self):
        return f"<LedgerEntry({self.entry_type} ${self.amount} on {self.entry_date})>"
