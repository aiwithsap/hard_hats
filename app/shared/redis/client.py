"""Redis connection factory."""

import os
from typing import Optional

import redis.asyncio as redis

# Redis URL from environment (Railway provides this)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Global client instance
_redis_client: Optional[redis.Redis] = None


class RedisClient:
    """Wrapper for Redis client with connection management."""

    def __init__(self, url: str = REDIS_URL):
        self.url = url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> redis.Redis:
        """Connect to Redis."""
        if self._client is None:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=False,  # We handle binary data for frames
            )
        return self._client

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> Optional[redis.Redis]:
        """Get the underlying Redis client."""
        return self._client


async def get_redis() -> redis.Redis:
    """Get or create global Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=False,
        )
    return _redis_client


async def close_redis() -> None:
    """Close global Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
