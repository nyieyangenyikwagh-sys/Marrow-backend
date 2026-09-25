import secrets
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.card import Card
from app.models.account import Account
from app.models.customer import Customer
from app.core.constants import AccountStatus, CardStatus, KYCStatus, CustomerStatus
from app.services.audit_service import AuditService


class CardService:
    """Sandbox card metadata only; no PAN or CVV is issued or stored."""
    @staticmethod
    async def create(db, customer_id, data):
        account = await db.scalar(select(Account).where(Account.id == data.account_id).with_for_update())
        if not account or account.customer_id != customer_id or account.is_internal:
            raise ValueError("Account not found")
        if account.account_status != AccountStatus.ACTIVE:
            raise ValueError("Account is not active")
        customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
        if customer.kyc_status != KYCStatus.VERIFIED or customer.customer_status != CustomerStatus.ACTIVE:
            raise PermissionError("Active, verified customer required")
        now = datetime.now(timezone.utc)
        expiry = now.replace(year=now.year + 3, day=1)
        card = Card(customer_id=customer_id, account_id=account.id, card_type="virtual",
                    card_number_encrypted="sandbox-no-pan", cvv_encrypted="not-stored",
                    card_last_4=f"{secrets.randbelow(10000):04d}", expiry_month=expiry.month,
                    expiry_year=expiry.year, expiry_date=expiry, is_virtual=True,
                    card_holder_name=data.card_holder_name, daily_limit=data.daily_limit,
                    monthly_limit=data.monthly_limit)
        db.add(card)
        await db.flush()
        await AuditService.log_action(db, entity_type="card", entity_id=card.id, action="sandbox_card_created",
                                      actor_id=customer_id, actor_type="customer")
        return card

    @staticmethod
    async def set_status(db, customer_id, card_id, target):
        card = await db.scalar(select(Card).where(Card.id == card_id, Card.customer_id == customer_id).with_for_update())
        if not card:
            raise ValueError("Card not found")
        if card.card_status == CardStatus.CANCELLED:
            raise ValueError("Cancelled cards cannot be changed")
        old = card.card_status
        card.card_status = target
        await AuditService.log_action(db, entity_type="card", entity_id=card.id, action="status_changed",
            actor_id=customer_id, actor_type="customer", old_values={"status": old.value}, new_values={"status": target.value})
        return card
