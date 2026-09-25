from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.base import ORMBase
from app.core.constants import KYCStatus, CustomerType, CustomerStatus, RiskLevel

class CustomerCreate(BaseModel):
    """Signup payload. Password lives here, never in a response schema."""
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    country: Optional[str] = None
    customer_type: CustomerType = CustomerType.PERSONAL

    @field_validator("password")
    @classmethod
    def password_minimum_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

class CustomerUpdate(BaseModel):
    """Partial update — every field optional. Notably excludes email,
    kyc_status, customer_status, risk_score, risk_level: identity and
    risk fields are never customer-editable, only admin/service-set."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

class CustomerResponse(ORMBase):
    """What a customer sees about themselves. Excludes risk_score and
    risk_level deliberately — a bank does not show customers their own
    internal AML risk rating (§9.1's allow-list principle applied)."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    date_of_birth: Optional[date]
    country: Optional[str]
    kyc_status: KYCStatus
    customer_type: CustomerType
    customer_status: CustomerStatus
    created_at: datetime

class CustomerAdminResponse(CustomerResponse):
    """What an admin/compliance user sees — everything CustomerResponse
    has, plus the risk fields it deliberately withholds. A separate
    class, not a flag on one class, so the allow-list is visible in the
    type itself rather than in conditional logic at the call site."""
    risk_score: int
    risk_level: RiskLevel
    kyc_verified_at: Optional[datetime]
