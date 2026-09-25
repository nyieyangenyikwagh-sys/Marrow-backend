from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy import Uuid as UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base
from app.core.constants import UserRole

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)

    role = Column(SQLEnum(UserRole), default=UserRole.SUPPORT)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
