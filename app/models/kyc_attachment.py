import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Uuid, String, Integer, LargeBinary, DateTime, ForeignKey
from app.core.database import Base


class KYCAttachment(Base):
    __tablename__ = "kyc_attachments"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id = Column(Uuid, ForeignKey("customers.id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)
    content_type = Column(String(50), nullable=False)
    size = Column(Integer, nullable=False)
    encrypted_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
