from uuid import UUID
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import require_role, get_current_admin
from app.core.constants import UserRole, VerificationStatus, TransactionStatus
from app.models import Customer, Account, Transaction, KYCDocument, AMLCheck, AuditLog, LedgerEntry
from app.schemas.base import ORMBase
from app.schemas.transaction import TransactionResponse
from app.schemas.aml import AMLCheckResponse
from app.schemas.kyc import KYCDocumentResponse
from app.core.encryption import EncryptionService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["admin"])
reviewer = require_role(UserRole.ADMIN, UserRole.COMPLIANCE)


class QueueDocument(KYCDocumentResponse):
    customer_id: UUID
    created_at: datetime


class AuditResponse(ORMBase):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor_id: UUID | None
    actor_type: str
    old_values: dict | None
    new_values: dict | None
    created_at: datetime


@router.get("/me")
async def me(staff=Depends(get_current_admin)):
    return dict(id=str(staff.id), first_name=staff.first_name, last_name=staff.last_name, role=staff.role, email=staff.email)


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db), staff=Depends(get_current_admin)):
    customers = await db.scalar(select(func.count()).select_from(Customer))
    accounts = await db.scalar(select(func.count()).select_from(Account).where(Account.is_internal.is_(False)))
    pending = await db.scalar(select(func.count()).select_from(Transaction).where(Transaction.status == TransactionStatus.PENDING))
    kyc = await db.scalar(select(func.count()).select_from(KYCDocument).where(KYCDocument.verification_status == VerificationStatus.PENDING))
    return dict(customers=customers, accounts=accounts, pending_transfers=pending, pending_kyc=kyc)


@router.get("/transactions", response_model=list[TransactionResponse])
async def transactions(status: TransactionStatus | None = None, limit: int = Query(50, ge=1, le=100),
                       offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    query = select(Transaction)
    if status:
        query = query.where(Transaction.status == status)
    return (await db.scalars(query.order_by(Transaction.transaction_date.desc()).limit(limit).offset(offset))).all()


@router.get("/kyc", response_model=list[QueueDocument])
async def kyc_queue(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                    db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    return (await db.scalars(select(KYCDocument).where(KYCDocument.verification_status == VerificationStatus.PENDING)
                            .order_by(KYCDocument.created_at).limit(limit).offset(offset))).all()


@router.get("/kyc/{document_id}")
async def kyc_document(document_id: UUID, db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    doc = await db.get(KYCDocument, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    result = {field: EncryptionService.decrypt(getattr(doc, field)) if getattr(doc, field) else None
              for field in ("document_number", "document_front_url", "document_back_url", "selfie_url")}
    await AuditService.log_action(db, entity_type="kyc", entity_id=doc.id, action="sensitive_document_viewed",
                                  actor_id=staff.id, actor_type="admin")
    await db.commit()
    return result


@router.get("/aml", response_model=list[AMLCheckResponse])
async def aml(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
              db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    return (await db.scalars(select(AMLCheck).order_by(AMLCheck.checked_at.desc()).limit(limit).offset(offset))).all()


@router.get("/audit", response_model=list[AuditResponse])
async def audit(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    return (await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))).all()
