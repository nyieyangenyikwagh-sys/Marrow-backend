from datetime import date, datetime, timezone
from sqlalchemy import select
from app.models.kyc import KYCDocument
from app.models.customer import Customer
from app.core.constants import KYCStatus, VerificationStatus
from app.core.encryption import EncryptionService
from app.services.audit_service import AuditService


class KYCService:
    @staticmethod
    async def submit(db, customer_id, data):
        customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
        if customer.kyc_status == KYCStatus.VERIFIED:
            raise ValueError("Identity is already verified")
        if data.expiry_date and data.expiry_date <= date.today():
            raise ValueError("Identity document has expired")
        if data.issue_date and data.issue_date > date.today():
            raise ValueError("Issue date cannot be in the future")
        pending = await db.scalar(select(KYCDocument.id).where(KYCDocument.customer_id == customer_id,
                                  KYCDocument.verification_status == VerificationStatus.PENDING))
        if pending:
            raise ValueError("A document is already awaiting review")
        values = data.model_dump()
        for field in ("document_number", "document_front_url", "document_back_url", "selfie_url"):
            if values.get(field):
                values[field] = EncryptionService.encrypt(values[field])
        doc = KYCDocument(customer_id=customer_id, **values)
        db.add(doc)
        customer.kyc_status = KYCStatus.PENDING
        await db.flush()
        await AuditService.log_action(db, entity_type="kyc", entity_id=doc.id, action="submitted",
                                      actor_id=customer_id, actor_type="customer")
        return doc

    @staticmethod
    async def review(db, document_id, staff_id, approve, notes):
        doc = await db.scalar(select(KYCDocument).where(KYCDocument.id == document_id).with_for_update())
        if not doc or doc.verification_status != VerificationStatus.PENDING:
            raise ValueError("Pending document not found")
        customer = await db.scalar(select(Customer).where(Customer.id == doc.customer_id).with_for_update())
        if approve and doc.expiry_date and doc.expiry_date <= date.today():
            raise ValueError("Document has expired")
        now = datetime.now(timezone.utc)
        doc.verification_status = VerificationStatus.APPROVED if approve else VerificationStatus.REJECTED
        doc.verified_by = staff_id
        doc.verified_at = now if approve else None
        doc.rejection_reason = None if approve else notes
        doc.is_document_valid = doc.is_selfie_match = approve
        customer.kyc_status = KYCStatus.VERIFIED if approve else KYCStatus.REJECTED
        customer.kyc_verified_at = now if approve else None
        await AuditService.log_action(db, entity_type="kyc", entity_id=doc.id,
            action="approved" if approve else "rejected", actor_id=staff_id, actor_type="admin",
            new_values={"notes": notes})
        return doc
