from sqlalchemy import Column, String, Integer, Date, DateTime, Enum as SQLEnum
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import KYCStatus, CustomerType, CustomerStatus, RiskLevel

class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)

    street_address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(2), nullable=True)

    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.PENDING, index=True)
    kyc_verified_at = Column(DateTime(timezone=True), nullable=True)
    kyc_document_url = Column(String(255), nullable=True)

    customer_type = Column(SQLEnum(CustomerType), default=CustomerType.PERSONAL)
    customer_status = Column(SQLEnum(CustomerStatus), default=CustomerStatus.ACTIVE)

    risk_score = Column(Integer, default=0)  # 0-100
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.LOW)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    accounts = relationship("Account", back_populates="customer")
    kyc_documents = relationship("KYCDocument", back_populates="customer")
