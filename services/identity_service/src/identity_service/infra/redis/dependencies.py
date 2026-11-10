from redis.asyncio import Redis

from identity_service.infra.redis.client import redis_client


def get_redis_client() -> Redis:
    return redis_client


# def get_redis_cache(
#     redis: Redis = Depends(get_redis_client)
# ) -> JsonCache:
#     return JsonCache(
#         redis=redis,
#         key_prefix=settings.redis_key_prefix,
#     )
