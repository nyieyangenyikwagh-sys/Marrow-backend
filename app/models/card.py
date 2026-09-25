from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import CardStatus

class Card(Base):
    __tablename__ = "cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)

    card_type = Column(String(50), nullable=False)  # virtual, debit, credit — descriptive only, §8.2
    card_number_encrypted = Column(String(255), nullable=False)
    card_last_4 = Column(String(4), nullable=False)

    expiry_month = Column(Integer, nullable=False)
    expiry_year = Column(Integer, nullable=False)
    cvv_encrypted = Column(String(255), nullable=False)

    card_status = Column(SQLEnum(CardStatus), default=CardStatus.ACTIVE)
    is_primary = Column(Boolean, default=False)
    is_virtual = Column(Boolean, default=False)

    daily_limit = Column(Numeric(20, 2), nullable=True)
    monthly_limit = Column(Numeric(20, 2), nullable=True)
    daily_spent = Column(Numeric(20, 2), default=0)
    monthly_spent = Column(Numeric(20, 2), default=0)
    last_reset_date = Column(DateTime(timezone=True), nullable=True)

    card_holder_name = Column(String(255), nullable=False)
    card_design = Column(String(100), default="standard")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expiry_date = Column(DateTime(timezone=True), nullable=False)
    blocked_at = Column(DateTime(timezone=True), nullable=True)

    account = relationship("Account", back_populates="cards")
