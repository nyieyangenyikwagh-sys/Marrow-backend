from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.core.config import settings

_database_url = settings.DATABASE_URL
if _database_url.startswith("postgresql://"):
    _database_url = _database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _database_url,
    echo=settings.SQLALCHEMY_ECHO,
    future=True,
    pool_pre_ping=True,   # added — see rationale below
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
