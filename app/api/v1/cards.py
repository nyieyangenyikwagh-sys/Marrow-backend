from uuid import UUID
from pydantic import BaseModel
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
