from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, or_, cast, String, Uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import require_role, get_current_admin
from app.core.constants import UserRole, VerificationStatus, TransactionStatus
from app.models import Customer, Account, Transaction, KYCDocument, AMLCheck, AuditLog
from app.schemas.base import ORMBase
from app.schemas.transaction import TransactionResponse
from app.schemas.aml import AMLCheckResponse
from app.schemas.kyc import KYCDocumentResponse
from app.core.encryption import EncryptionService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["admin"])
reviewer = require_role(UserRole.ADMIN, UserRole.COMPLIANCE)


def search_fields(model, fields, query):
    clauses = []
    for name in fields:
        field = getattr(model, name)
        value = cast(field, String)
        if isinstance(field.type, Uuid):
            clauses.append(func.replace(value, "-", "").icontains(query.replace("-", ""), autoescape=True))
        else:
            clauses.append(value.icontains(query, autoescape=True))
    return or_(*clauses)


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
    return (await db.scalars(query.order_by(Transaction.transaction_date.desc(), Transaction.id).limit(limit).offset(offset))).all()


@router.get("/kyc", response_model=list[QueueDocument])
async def kyc_queue(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                    db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    return (await db.scalars(select(KYCDocument).where(KYCDocument.verification_status == VerificationStatus.PENDING)
                            .order_by(KYCDocument.created_at, KYCDocument.id).limit(limit).offset(offset))).all()


@router.get("/kyc/{document_id}")
async def kyc_document(document_id: UUID, db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    doc = await db.get(KYCDocument, document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    result = {field: EncryptionService.decrypt(getattr(doc, field)) if getattr(doc, field) else None
              for field in ("document_number", "document_front_url", "document_back_url", "selfie_url")}
    result.update(issue_date=doc.issue_date.isoformat() if doc.issue_date else None,
                  expiry_date=doc.expiry_date.isoformat() if doc.expiry_date else None)
    await AuditService.log_action(db, entity_type="kyc", entity_id=doc.id, action="sensitive_document_viewed",
                                  actor_id=staff.id, actor_type="admin")
    await db.commit()
    return result


@router.get("/aml", response_model=list[AMLCheckResponse])
async def aml(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
              resolution: str | None = None,
              db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    query = select(AMLCheck)
    if resolution:
        from app.core.constants import AMLResolution
        query = query.where(AMLCheck.resolution == AMLResolution(resolution))
    return (await db.scalars(query.order_by(AMLCheck.checked_at.desc(), AMLCheck.id).limit(limit).offset(offset))).all()


@router.get("/audit", response_model=list[AuditResponse])
async def audit(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                q: str = Query("", max_length=100),
                db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    query = select(AuditLog)
    if q:
        query = query.where(search_fields(AuditLog, ("action", "entity_type", "entity_id", "actor_id"), q))
    return (await db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit).offset(offset))).all()


@router.get("/attachments/{attachment_id}")
async def attachment(attachment_id: UUID, db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    from fastapi.responses import Response
    from app.models import KYCAttachment
    item = await db.get(KYCAttachment, attachment_id)
    if not item:
        raise HTTPException(404, "Attachment not found")
    await AuditService.log_action(db, entity_type="kyc_attachment", entity_id=item.id,
                                  action="sensitive_file_viewed", actor_id=staff.id, actor_type="admin")
    content = EncryptionService._get_cipher().decrypt(item.encrypted_data)
    extension = {"image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf"}[item.content_type]
    await db.commit()
    return Response(content, media_type=item.content_type,
                    headers={"Content-Disposition": f'attachment; filename="identity-{item.id}.{extension}"'})


@router.get("/customers")
async def customer_directory(q: str = Query("", max_length=100), limit: int = Query(25, ge=1, le=100),
                             offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db), staff=Depends(get_current_admin)):
    query = select(Customer).where(~Customer.accounts.any(Account.is_internal.is_(True)))
    if q:
        query = query.where(search_fields(Customer, ("id", "email", "first_name", "last_name"), q))
    rows = (await db.scalars(query.order_by(Customer.created_at.desc(), Customer.id).limit(limit).offset(offset))).all()
    return [{field: getattr(row, field) for field in ("id", "first_name", "last_name", "email", "kyc_status",
             "customer_status", "risk_score", "risk_level")} for row in rows]


@router.get("/accounts")
async def account_directory(q: str = Query("", max_length=100), limit: int = Query(25, ge=1, le=100),
                            offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    from app.schemas.account import AccountResponse
    query = select(Account).where(Account.is_internal.is_(False))
    if q:
        query = query.where(search_fields(Account, ("id", "customer_id", "account_number", "account_name"), q))
    rows = (await db.scalars(query.order_by(Account.created_at.desc(), Account.id).limit(limit).offset(offset))).all()
    return [dict(AccountResponse.model_validate(row).model_dump(), customer_id=row.customer_id) for row in rows]


class RiskUpdate(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=3, max_length=500)


@router.patch("/customers/{customer_id}/risk")
async def update_risk(customer_id: UUID, data: RiskUpdate, db: AsyncSession = Depends(get_db), staff=Depends(reviewer)):
    from app.core.constants import RiskLevel, AMLResolution
    from app.core.config import settings
    from datetime import timezone
    customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if not customer:
        raise HTTPException(404, "Customer not found")
    if await db.scalar(select(Account.id).where(Account.customer_id == customer_id, Account.is_internal.is_(True)).limit(1)):
        raise ValueError("System customers cannot be changed")
    previous = {"score": customer.risk_score, "level": customer.risk_level.value}
    level = (RiskLevel.HIGH if data.score >= settings.AML_HIGH_RISK_THRESHOLD else
             RiskLevel.MEDIUM if data.score >= settings.AML_MEDIUM_RISK_THRESHOLD else RiskLevel.LOW)
    customer.risk_score, customer.risk_level = data.score, level
    check = AMLCheck(customer_id=customer_id, check_type="customer", risk_score=data.score, risk_level=level,
                     flags_triggered=["manual_risk_assessment"], resolution=AMLResolution.APPROVED,
                     resolved_at=datetime.now(timezone.utc), resolved_by=staff.id, resolution_notes=data.reason)
    db.add(check)
    await AuditService.log_action(db, entity_type="customer", entity_id=customer_id, action="risk_assessed",
                                  actor_id=staff.id, actor_type="admin", old_values=previous,
                                  new_values={"score": data.score, "level": level.value, "reason": data.reason})
    await db.commit()
    return {"risk_score": data.score, "risk_level": level.value}
