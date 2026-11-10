from redis.asyncio import Redis

from identity_service.infra.config import get_settings

redis_client = Redis.from_url(
    get_settings().redis_url,
    encoding="utf-8",
    decode_responses=True,
)


async def close_redis_client() -> None:
    await redis_client.aclose()
