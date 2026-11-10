# from dataclasses import dataclass

# from redis.asyncio import Redis


# @dataclass(frozen=True)
# class RateLimitResult:
#     allowed: bool
#     attempts: int
#     limit: int
#     degraded: bool = False  # <-- перемещено вперёд, добавлено значение по умолчанию
#     retry_after_seconds: int | None = None


# @dataclass
# class RedisFixedWindowRateLimiter:
#     redis: Redis
#     key_prefix: str

#     async def hit(
#         self,
#         *,
#         key: str,
#         limit: int,
#         window_seconds: int,
#     ) -> RateLimitResult:
#         redis_key = f"{self.key_prefix}:{key}"

#         try:
#             was_created = await self.redis.set(
#                 redis_key,
#                 1,
#                 ex=window_seconds,
#                 nx=True,
#             )
#             if was_created:
#                 attempts = 1
#             else:
#                 attempts = int(await self.redis.incr(redis_key))

#             if attempts <= limit:
#                 return RateLimitResult(
#                     allowed=True,
#                     attempts=attempts,
#                     limit=limit,
#                 )

#             ttl = await self.redis.ttl(redis_key)
#             retry_after_seconds = ttl if ttl > 0 else window_seconds

#             return RateLimitResult(
#                 allowed=False,
#                 attempts=attempts,
#                 limit=limit,
#                 retry_after_seconds=retry_after_seconds,
#             )
#         except Exception:
#             return RateLimitResult(
#                 allowed=True,
#                 attempts=0,
#                 limit=limit,
#                 degraded=True,
#             )
