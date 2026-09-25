from sqlalchemy import Column, String, Boolean, Float, DateTime, Date, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import DocumentType, VerificationStatus

class KYCDocument(Base):
    __tablename__ = "kyc_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)

    document_type = Column(SQLEnum(DocumentType), nullable=False)
    document_number = Column(Text, nullable=False)
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)

    document_front_url = Column(Text, nullable=False)
    document_back_url = Column(Text, nullable=True)
    selfie_url = Column(Text, nullable=False)

    verification_status = Column(SQLEnum(VerificationStatus), default=VerificationStatus.PENDING, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), nullable=True)

    rejection_reason = Column(Text, nullable=True)
    rejection_date = Column(DateTime(timezone=True), nullable=True)

    is_document_valid = Column(Boolean, default=False)
    is_selfie_match = Column(Boolean, default=False)
    liveness_score = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="kyc_documents")
