from datetime import datetime, timezone
from sqlalchemy import select
from app.models.transaction import Transaction
from app.models.aml import AMLCheck
from app.services.ledger_service import LedgerService
from app.services.transfer_service import TransferService
from app.services.audit_service import AuditService
from app.core.constants import TransactionStatus, AMLResolution
from app.core.state_machine import validate_transition


class TransactionService:
    @staticmethod
    async def get_by_id(db, transaction_id, lock=False):
        query = select(Transaction).where(Transaction.id == transaction_id).execution_options(populate_existing=True)
        if lock:
            query = query.with_for_update()
        row = await db.scalar(query)
        if not row:
            raise ValueError("Transaction not found")
        return row

    @staticmethod
    async def _review(db, transaction_id, staff_id, notes, approve):
        row = await TransactionService.get_by_id(db, transaction_id, lock=True)
        status = TransactionStatus.COMPLETED if approve else TransactionStatus.FAILED
        validate_transition(row.status, status)
        if approve:
            accounts = await TransferService.lock_accounts(db, [row.from_account_id, row.to_account_id])
            source, destination = accounts[row.from_account_id], accounts[row.to_account_id]
            await TransferService.validate_accounts(db, source, destination, row.amount, row.fee_amount, row.id)
            await TransferService.post(db, row, source, destination)
            row.completed_at = datetime.now(timezone.utc)
        row.status = status
        check = await db.scalar(select(AMLCheck).where(AMLCheck.transaction_id == row.id).with_for_update())
        if check:
            check.resolution = AMLResolution.APPROVED if approve else AMLResolution.BLOCKED
            check.resolved_at, check.resolved_by, check.resolution_notes = datetime.now(timezone.utc), staff_id, notes
        await AuditService.log_action(db, entity_type="transaction", entity_id=row.id,
            action="review_approved" if approve else "review_rejected", actor_id=staff_id, actor_type="admin",
            old_values={"status": "pending"}, new_values={"status": status.value, "notes": notes})
        return row

    @staticmethod
    async def review_approve(db, transaction_id, staff_id, notes):
        return await TransactionService._review(db, transaction_id, staff_id, notes, True)

    @staticmethod
    async def review_reject(db, transaction_id, staff_id, notes):
        return await TransactionService._review(db, transaction_id, staff_id, notes, False)

    @staticmethod
    async def reverse(db, transaction_id, staff_id, reason):
        row = await TransactionService.get_by_id(db, transaction_id, lock=True)
        validate_transition(row.status, TransactionStatus.REVERSED)
        reversal = await LedgerService.reverse_transaction(db, transaction_id, reason, staff_id)
        await AuditService.log_action(db, entity_type="transaction", entity_id=row.id, action="reversed",
            actor_id=staff_id, actor_type="admin", new_values={"reversal_id": str(reversal.id), "reason": reason})
        return reversal
