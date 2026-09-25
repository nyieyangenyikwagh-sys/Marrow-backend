from uuid import UUID
from pydantic import BaseModel, Field
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user
from app.core.constants import CardStatus
from app.models.card import Card
from app.schemas.card import CreateCardRequest, CardResponse
from app.services.card_service import CardService

router = APIRouter(prefix="/cards", tags=["cards"])


class StatusRequest(BaseModel):
    status: CardStatus


class CardLimits(BaseModel):
    daily_limit: Decimal | None = Field(None, gt=0, max_digits=20, decimal_places=2)
    monthly_limit: Decimal | None = Field(None, gt=0, max_digits=20, decimal_places=2)


@router.patch("/{card_id}/limits", response_model=CardResponse)
async def update_limits(card_id: UUID, data: CardLimits, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    from app.services.audit_service import AuditService
    card = await db.scalar(select(Card).where(Card.id == card_id, Card.customer_id == user.id).with_for_update())
    if not card or card.card_status == CardStatus.CANCELLED:
        raise ValueError("An editable card was not found")
    values = data.model_dump(exclude_unset=True)
    if not values:
        raise ValueError("Provide at least one limit")
    old = {field: getattr(card, field) for field in values}
    for field, value in values.items():
        setattr(card, field, value)
    await AuditService.log_action(db, entity_type="card", entity_id=card.id, action="limits_changed",
                                  actor_id=user.id, actor_type="customer", old_values=old, new_values=values)
    await db.commit()
    return card


@router.get("", response_model=list[CardResponse])
async def list_cards(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return (await db.scalars(select(Card).where(Card.customer_id == user.id).order_by(Card.created_at.desc()))).all()


@router.post("", response_model=CardResponse, status_code=201)
async def create(data: CreateCardRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    card = await CardService.create(db, user.id, data)
    await db.commit()
    return card


@router.patch("/{card_id}/status", response_model=CardResponse)
async def update_status(card_id: UUID, data: StatusRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    card = await CardService.set_status(db, user.id, card_id, data.status)
    await db.commit()
    return card
