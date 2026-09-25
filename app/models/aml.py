from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy import Uuid as UUID, JSON
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import RiskLevel, AMLResolution

class AMLCheck(Base):
    __tablename__ = "aml_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True, index=True)

    check_type = Column(String(50), nullable=False)

    risk_score = Column(Integer, default=0)
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.LOW)

    flags_triggered = Column(JSON, default=list)

    resolution = Column(SQLEnum(AMLResolution), default=AMLResolution.PENDING)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    resolution_notes = Column(String(500), nullable=True)

    checked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index('idx_customer_id_risk', 'customer_id', 'risk_level'),
        Index('idx_resolution', 'resolution'),
    )
