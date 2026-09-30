"""Asynchronous Redis Client and Distributed Locking Facility.

Provides session management, token-bucket rate limiting, and cluster locking.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional
import redis.asyncio as aioredis
from src.common.config.settings import get_settings
from src.common.exceptions.base import RedisLockError
from src.common.logging.logger import get_logger

logger = get_logger("database.redis")
settings = get_settings()

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=50,
    decode_responses=True,
)


def get_redis_client() -> aioredis.Redis:
    """Instantiate a Redis client instance from the shared connection pool."""
    return aioredis.Redis(connection_pool=redis_pool)


async def check_redis_health() -> bool:
    """Ping Redis instance to confirm responsiveness."""
    client = get_redis_client()
    try:
        response = await client.ping()
        return bool(response)
    except Exception as exc:
        logger.error("Redis ping failed", error=str(exc))
        return False
    finally:
        await client.aclose()


@asynccontextmanager
async def acquire_distributed_lock(
    lock_key: str,
    timeout_seconds: int = 10,
    blocking_timeout: int = 5,
) -> AsyncGenerator[bool, None]:
    """Distributed lock context manager to prevent concurrent ETL or report executions."""
    client = get_redis_client()
    lock = client.lock(
        f"lock:{lock_key}",
        timeout=timeout_seconds,
        blocking_timeout=blocking_timeout,
    )
    acquired = False
    try:
        acquired = await lock.acquire()
        if not acquired:
            raise RedisLockError(
                f"Failed to acquire distributed lock for resource: {lock_key}",
                details={"lock_key": lock_key, "timeout": timeout_seconds},
            )
        logger.debug("Acquired distributed lock", key=lock_key)
        yield acquired
    except Exception as exc:
        logger.error("Error within distributed lock scope", key=lock_key, error=str(exc))
        raise
    finally:
        if acquired:
            try:
                await lock.release()
                logger.debug("Released distributed lock", key=lock_key)
            except Exception as release_exc:
                logger.warning("Could not release lock cleanly", key=lock_key, error=str(release_exc))
        await client.aclose()
