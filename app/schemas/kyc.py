from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.schemas.base import ORMBase

from app.core.constants import DocumentType, VerificationStatus, KYCStatus

class KYCSubmitRequest(BaseModel):
    document_type: DocumentType
    document_number: str = Field(min_length=1, max_length=100)
    document_front_url: str
    document_back_url: Optional[str] = None
    selfie_url: str
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None

    @field_validator("document_front_url", "document_back_url", "selfie_url")
    @classmethod
    def document_link(cls, value):
        from urllib.parse import urlparse
        if value and value.startswith("attachment:"):
            UUID(value.removeprefix("attachment:"))
            return value
        if value is not None and (len(value) > 2048 or urlparse(value).scheme not in {"https", "http"} or not urlparse(value).netloc):
            raise ValueError("Document references must be HTTP(S) URLs")
        return value

class KYCDocumentResponse(ORMBase):
    id: UUID
    document_type: DocumentType
    verification_status: VerificationStatus
    verified_at: Optional[datetime]

class KYCStatusResponse(BaseModel):
    customer_id: UUID
    kyc_status: KYCStatus
    kyc_verified_at: Optional[datetime]
    latest_document: Optional[KYCDocumentResponse]
