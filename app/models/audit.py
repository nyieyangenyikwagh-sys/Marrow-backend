from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy import Uuid as UUID, JSON
from datetime import datetime, timezone
import uuid

from app.core.database import Base

class AuditLog(Base):
    """Append-only, per §1.3/§1.8 — never updated, never deleted."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    action = Column(String(50), nullable=False)

    actor_id = Column(UUID(as_uuid=True), nullable=True)
    actor_type = Column(String(50), nullable=False)

    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    changes_description = Column(Text, nullable=True)

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
