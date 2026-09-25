from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
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


@router.post("/attachments", status_code=201)
async def upload_attachment(file: UploadFile = File(...), role: str = Form(...),
                            db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    from sqlalchemy import func
    from app.models import Customer, KYCAttachment
    from app.core.encryption import EncryptionService
    from app.services.audit_service import AuditService
    if role not in {"front", "back", "selfie"}:
        raise ValueError("Invalid document role")
    data = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if not data or len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Each file must be between 1 byte and 5 MB")
    content_type = ("image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else
                    "image/jpeg" if data.startswith(b"\xff\xd8\xff") else
                    "application/pdf" if data.startswith(b"%PDF-") else None)
    if not content_type or (role == "selfie" and content_type == "application/pdf"):
        raise ValueError("Use PNG or JPEG images, or PDF for identity documents")
    await db.scalar(select(Customer).where(Customer.id == user.id).with_for_update())
    count = await db.scalar(select(func.count()).select_from(KYCAttachment).where(KYCAttachment.customer_id == user.id))
    if count >= 20:
        raise ValueError("Identity upload quota reached; contact support")
    attachment = KYCAttachment(customer_id=user.id, role=role, content_type=content_type,
                               size=len(data), encrypted_data=EncryptionService._get_cipher().encrypt(data))
    db.add(attachment)
    await db.flush()
    await AuditService.log_action(db, entity_type="kyc_attachment", entity_id=attachment.id,
                                  action="uploaded", actor_id=user.id, actor_type="customer")
    await db.commit()
    return {"id": str(attachment.id), "reference": f"attachment:{attachment.id}"}


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
