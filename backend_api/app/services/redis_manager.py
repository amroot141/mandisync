import json
import logging
from typing import Any, Optional, Dict
import redis.asyncio as redis

from backend_api.app.core.config import settings

logger = logging.getLogger("mandisync.redis")

class RedisManager:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.is_connected: bool = False

    async def connect(self):
        logger.info("Connecting to Redis...")
        try:
            self.client = redis.from_url(
                settings.REDIS_URI, 
                encoding="utf-8", 
                decode_responses=True
            )
            # Ping to verify connection
            await self.client.ping()
            self.is_connected = True
            logger.info("Successfully connected to Redis")
        except Exception as exc:
            self.is_connected = False
            logger.warning(f"Could not connect to Redis: {exc}. Application will bypass cache.")

    async def close(self):
        if self.client:
            logger.info("Closing Redis connection...")
            await self.client.close()
            self.is_connected = False

    async def get_cache(self, key: str) -> Optional[Any]:
        if not self.is_connected or not self.client:
            return None
        try:
            data = await self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as exc:
            logger.warning(f"Redis GET error: {exc}")
            return None

    async def set_cache(self, key: str, value: Any, expire_seconds: int = 300):
        if not self.is_connected or not self.client:
            return
        try:
            serialized_data = json.dumps(value)
            await self.client.set(key, serialized_data, ex=expire_seconds)
        except Exception as exc:
            logger.warning(f"Redis SET error: {exc}")

    async def delete_cache(self, key: str):
        if not self.is_connected or not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as exc:
            logger.warning(f"Redis DELETE error: {exc}")

    async def delete_pattern(self, pattern: str):
        if not self.is_connected or not self.client:
            return
        try:
            # Use SCAN to find keys matching pattern and delete them
            cursor = '0'
            while cursor != 0:
                cursor, keys = await self.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await self.client.delete(*keys)
        except Exception as exc:
            logger.warning(f"Redis DELETE pattern error: {exc}")


redis_manager = RedisManager()
