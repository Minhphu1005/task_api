import fnmatch
import json
import logging
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger("taskhub.cache")
RECONNECT_INTERVAL_SECONDS = 30.0


class CacheService:
    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._memory: dict[str, tuple[str, float]] = {}
        self._last_connect_attempt: float = 0.0

    @property
    def redis_client(self) -> Redis | None:
        return self._redis

    async def connect(self) -> None:
        settings = get_settings()
        self._last_connect_attempt = time.monotonic()
        try:
            client: Redis = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                socket_timeout=settings.redis_socket_timeout,
                retry_on_timeout=True,
            )
            await client.ping()
            self._redis = client
            logger.info("Connected to Redis cache at %s", settings.redis_url)
        except Exception as exc:
            self._redis = None
            logger.warning("Redis unavailable (%s); falling back to in-memory cache", exc)

    async def _maybe_reconnect(self) -> None:
        if self._redis is not None:
            return
        if get_settings().environment == "test":
            return
        if time.monotonic() - self._last_connect_attempt >= RECONNECT_INTERVAL_SECONDS:
            await self.connect()

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._memory.items() if now >= exp]
        for key in expired:
            self._memory.pop(key, None)

    async def get_json(self, key: str) -> Any | None:
        await self._maybe_reconnect()
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw is not None else None
            except RedisError as exc:
                logger.warning("Redis GET failed for %s: %s", key, exc)

        self._evict_expired()
        entry = self._memory.get(key)
        if entry is None:
            return None
        return json.loads(entry[0])

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        await self._maybe_reconnect()
        ttl = ttl_seconds if ttl_seconds is not None else get_settings().cache_ttl_seconds
        payload = json.dumps(value, default=str)
        if self._redis is not None:
            try:
                await self._redis.set(key, payload, ex=max(ttl, 1))
                return
            except RedisError as exc:
                logger.warning("Redis SET failed for %s: %s", key, exc)

        self._memory[key] = (payload, time.monotonic() + max(ttl, 1))

    async def delete_pattern(self, pattern: str) -> int:
        await self._maybe_reconnect()
        deleted = 0
        if self._redis is not None:
            try:
                keys: list[str] = [k async for k in self._redis.scan_iter(match=pattern)]
                if keys:
                    deleted = int(await self._redis.delete(*keys))
                return deleted
            except RedisError as exc:
                logger.warning("Redis DELETE pattern failed for %s: %s", pattern, exc)

        self._evict_expired()
        matched = [k for k in self._memory if fnmatch.fnmatch(k, pattern)]
        for key in matched:
            self._memory.pop(key, None)
        return len(matched)

    def clear_memory(self) -> None:
        self._memory.clear()


cache_service = CacheService()


def project_tasks_cache_key(
    project_id: int,
    *,
    status: str | None,
    priority: str | None,
    assignee_id: int | None,
    search: str | None,
    page: int,
    limit: int,
) -> str:
    return (
        f"project:{project_id}:tasks:"
        f"status={status or '*'}:priority={priority or '*'}:"
        f"assignee={assignee_id if assignee_id is not None else '*'}:"
        f"search={search or '*'}:page={page}:limit={limit}"
    )


async def invalidate_project_tasks_cache(project_id: int) -> None:
    await cache_service.delete_pattern(f"project:{project_id}:tasks:*")
