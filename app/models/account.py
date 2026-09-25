from sqlalchemy import Column, String, Numeric, Boolean, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import AccountType, AccountStatus

class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)

    account_name = Column(String(100), nullable=False)
    account_number = Column(String(64), unique=True, nullable=False, index=True)
    account_type = Column(SQLEnum(AccountType), nullable=False)
    currency_code = Column(String(3), nullable=False)

    account_status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE)
    is_primary = Column(Boolean, default=False)

    is_internal = Column(Boolean, default=False, index=True)

    daily_limit = Column(Numeric(20, 2), nullable=True)
    monthly_limit = Column(Numeric(20, 2), nullable=True)
    transaction_limit = Column(Numeric(20, 2), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_customer_id_account_number', 'customer_id', 'account_number'),
    )

    customer = relationship("Customer", back_populates="accounts")
    cards = relationship("Card", back_populates="account")
