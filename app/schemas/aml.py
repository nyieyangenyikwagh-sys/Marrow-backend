from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from app.schemas.base import ORMBase

from app.core.constants import RiskLevel, AMLResolution

class AMLCheckResponse(ORMBase):
    """Admin/compliance-facing only — there is no customer-facing AML
    schema anywhere in this system; a customer is never shown their own
    AML check results directly (only its downstream effect, e.g. a
    transaction sitting in 'pending' for review)."""
    id: UUID
    customer_id: Optional[UUID]
    transaction_id: Optional[UUID]
    check_type: str
    risk_score: int
    risk_level: RiskLevel
    flags_triggered: List[str]
    resolution: AMLResolution
    resolution_notes: Optional[str]
    checked_at: datetime
