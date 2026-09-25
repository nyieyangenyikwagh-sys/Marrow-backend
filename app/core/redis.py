from redis.asyncio import Redis
from app.core.config import settings

client = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


async def get_redis():
    return client
