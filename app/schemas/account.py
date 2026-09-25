from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMBase
from app.core.constants import AccountType, AccountStatus

class AccountCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    account_type: AccountType
    currency_code: str = "USD"
    daily_limit: Optional[Decimal] = None
    monthly_limit: Optional[Decimal] = None
    transaction_limit: Optional[Decimal] = None

    @field_validator("daily_limit", "monthly_limit", "transaction_limit")
    @classmethod
    def limits_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Limits must be a positive amount")
        return v

    @field_validator("currency_code")
    @classmethod
    def currency_code_format(cls, v: str) -> str:
        if len(v) != 3 or not v.isalpha():
            raise ValueError("currency_code must be a 3-letter ISO code, e.g. USD")
        if v.upper() not in {"CAD", "USD", "GBP", "EUR"}:
            raise ValueError("Supported currencies: CAD, USD, GBP, EUR")
        return v.upper()

class AccountResponse(ORMBase):
    id: UUID
    account_name: str
    account_number: str
    account_type: AccountType
    currency_code: str
    account_status: AccountStatus
    is_primary: bool
    daily_limit: Optional[Decimal]
    monthly_limit: Optional[Decimal]
    transaction_limit: Optional[Decimal]
    created_at: datetime
