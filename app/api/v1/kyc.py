from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.core.constants import UserRole
from app.models.kyc import KYCDocument
from app.schemas.kyc import KYCSubmitRequest, KYCDocumentResponse, KYCStatusResponse
from app.services.kyc_service import KYCService

router = APIRouter(prefix="/kyc", tags=["kyc"])


class ReviewRequest(BaseModel):
    approve: bool
    notes: str = Field(min_length=3, max_length=500)


@router.post("/documents", response_model=KYCDocumentResponse, status_code=201)
async def submit(data: KYCSubmitRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    doc = await KYCService.submit(db, user.id, data)
    await db.commit()
    return doc


@router.get("/status", response_model=KYCStatusResponse)
async def status(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    doc = await db.scalar(select(KYCDocument).where(KYCDocument.customer_id == user.id)
                          .order_by(KYCDocument.created_at.desc()).limit(1))
    return dict(customer_id=user.id, kyc_status=user.kyc_status,
                kyc_verified_at=user.kyc_verified_at, latest_document=doc)


@router.post("/{document_id}/review", response_model=KYCDocumentResponse)
async def review(document_id: UUID, data: ReviewRequest, db: AsyncSession = Depends(get_db),
                 staff=Depends(require_role(UserRole.ADMIN, UserRole.COMPLIANCE))):
    doc = await KYCService.review(db, document_id, staff.id, data.approve, data.notes)
    await db.commit()
    return doc
