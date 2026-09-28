from redis.asyncio import Redis
from app.core.config import settings
from app.core.local_sessions import LocalSessions

backend = settings.SESSION_BACKEND or ("sqlite" if settings.ENVIRONMENT == "development" else "redis")
client = (LocalSessions(settings.LOCAL_SESSION_DB) if backend == "sqlite" else
          Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2))


async def get_redis():
    return client
