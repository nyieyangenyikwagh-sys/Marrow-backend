from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMBase
from app.core.constants import TransactionType, TransactionStatus

class TransferRequest(BaseModel):
    """§9.0's fix applied: amount is Decimal, not float. The
    Decimal(str(...)) conversion dance that existed in the source
    router is no longer needed anywhere — Pydantic does the right
    conversion once, here, at the boundary."""
    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    description: str = Field(default="Transfer", min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$")

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Transfer amount must be positive")
        return v

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_reasonable_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 255:
            raise ValueError("idempotency_key must be 255 characters or fewer")
        return v

class TransactionResponse(ORMBase):
    id: UUID
    from_account_id: UUID
    to_account_id: Optional[UUID]
    transaction_type: TransactionType
    amount: Decimal
    currency_code: str
    fee_amount: Decimal
    status: TransactionStatus
    reference_number: Optional[str]
    reverses_transaction_id: Optional[UUID]   # surfaces §8.1 bug #7's new column
    transaction_date: datetime
    completed_at: Optional[datetime]
