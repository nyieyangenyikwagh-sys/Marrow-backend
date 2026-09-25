from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMBase
from app.core.constants import CardStatus

class CreateCardRequest(BaseModel):
    account_id: UUID
    card_holder_name: str = Field(min_length=1, max_length=100)
    daily_limit: Optional[Decimal] = None
    monthly_limit: Optional[Decimal] = None

    @field_validator("daily_limit", "monthly_limit")
    @classmethod
    def limits_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Card limits must be a positive amount")
        return v

class CardResponse(ORMBase):
    """§9.1's rule applied concretely: card_number_encrypted and
    cvv_encrypted are ORM fields that MUST NOT appear here. Only
    card_last_4 — enough for a customer to recognize their own card,
    never enough to reconstruct it."""
    id: UUID
    account_id: UUID
    card_type: str
    card_last_4: str
    expiry_month: int
    expiry_year: int
    card_status: CardStatus
    is_primary: bool
    is_virtual: bool
    daily_limit: Optional[Decimal]
    monthly_limit: Optional[Decimal]
    card_holder_name: str
    created_at: datetime
