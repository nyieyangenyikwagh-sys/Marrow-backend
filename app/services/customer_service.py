from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.models.customer import Customer
from app.core.constants import CustomerStatus
from app.schemas.customer import CustomerUpdate
from app.services.audit_service import AuditService

class CustomerService:

    @staticmethod
    async def get_by_id(db: AsyncSession, customer_id: UUID) -> Optional[Customer]:
        return await db.get(Customer, customer_id)

    @staticmethod
    async def update_profile(
        db: AsyncSession, customer_id: UUID, data: CustomerUpdate
    ) -> Customer:
        customer = await db.get(Customer, customer_id)
        if not customer:
            raise ValueError("Customer not found")

        updates = data.model_dump(exclude_unset=True)
        for name in ("first_name", "last_name"):
            if name in updates and (not updates[name] or len(updates[name]) > 100):
                raise ValueError("Names must contain 1 to 100 characters")
        old_values = {k: getattr(customer, k) for k in updates}
        for field, value in updates.items():
            setattr(customer, field, value)

        await AuditService.log_action(
            db=db, entity_type="customer", entity_id=customer.id, action="profile_update",
            actor_id=customer.id, actor_type="customer",
            old_values=old_values, new_values=updates,
        )
        return customer

    @staticmethod
    async def list_customers(
        db: AsyncSession, page: int = 1, page_size: int = 25,
        kyc_status: Optional[str] = None, customer_status: Optional[str] = None,
    ) -> tuple[list[Customer], int]:
        """Admin-facing paginated list. page_size is capped — see §11.4."""
        query = select(Customer)
        count_query = select(func.count()).select_from(Customer)

        if kyc_status:
            query = query.where(Customer.kyc_status == kyc_status)
            count_query = count_query.where(Customer.kyc_status == kyc_status)
        if customer_status:
            query = query.where(Customer.customer_status == customer_status)
            count_query = count_query.where(Customer.customer_status == customer_status)

        total = (await db.execute(count_query)).scalar()
        query = query.offset((page - 1) * page_size).limit(page_size)
        results = (await db.execute(query)).scalars().all()
        return list(results), total

    @staticmethod
    async def set_status(
        db: AsyncSession, customer_id: UUID, new_status: CustomerStatus,
        admin_id: UUID, reason: str,
    ) -> Customer:
        """Backs both freeze and unfreeze — one code path, one audit
        trail shape, for what is really the same operation in two
        directions. §1.5's guard ordering principle applies here too:
        freezing is the cheapest, most disqualifying check a transfer
        can hit, so it needs to be reliably reflected in customer_status
        the moment this commits."""
        customer = await db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update()
                                   .execution_options(populate_existing=True))
        if not customer:
            raise ValueError("Customer not found")
        if customer.customer_status == new_status:
            raise ValueError(f"Customer is already {new_status.value}")

        old_status = customer.customer_status
        customer.customer_status = new_status

        await AuditService.log_action(
            db=db, entity_type="customer", entity_id=customer.id,
            action=f"status_change_{new_status.value}",
            actor_id=admin_id, actor_type="admin",
            old_values={"customer_status": old_status.value},
            new_values={"customer_status": new_status.value, "reason": reason},
        )
        return customer
