"""
Redis velocity counter service.
Uses Redis Sorted Sets with sliding window for atomic velocity checks.
Falls back gracefully if Redis is unavailable.
"""

import time
import uuid
import redis.asyncio as aioredis
from typing import Optional, cast, Awaitable
import logging

logger = logging.getLogger(__name__)


class VelocityService:
    """Manages Redis-based velocity counters for IP and device tracking."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._connected = False
        self._memory_store = {}  # In-memory fallback for local Windows demo

    async def connect(self, redis_url: str):
        """Initialize Redis connection pool."""
        try:
            self._redis = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=1,
                retry_on_timeout=True,
            )
            # Test connection
            await cast(Awaitable[bool], self._redis.ping())
            self._connected = True
            logger.info("[REDIS] Connected successfully")
        except Exception as e:
            logger.warning(f"[REDIS] Connection failed: {e}. Using in-memory fallback for demo.")
            self._connected = False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:
                await self._redis.close()
            self._connected = False


    async def get_velocity(self, entity_type: str, entity_id: str, window_seconds: int) -> int:
        """
        Get the count of events for an entity within a sliding time window.
        Uses Redis Sorted Sets with atomic pipeline for thread safety.
        Falls back to an in-memory list if Redis is unavailable.

        Args:
            entity_type: "ip" or "device"
            entity_id: The IP address or device hash
            window_seconds: Time window in seconds (e.g., 900 for 15 min)

        Returns:
            Count of events in the window.
        """
        key = f"velocity:{entity_type}:{entity_id}"
        now = time.time()
        cutoff = now - window_seconds
        
        if not self._connected or not self._redis:
            # --- IN-MEMORY FALLBACK FOR DEMO ---
            if key not in self._memory_store:
                self._memory_store[key] = []
            
            # Filter out old timestamps
            self._memory_store[key] = [t for t in self._memory_store[key] if t > cutoff]
            # Add current timestamp
            self._memory_store[key].append(now)
            
            # Auto-cleanup memory store occasionally so it doesn't grow infinitely in dev
            if len(self._memory_store) > 1000:
                self._memory_store.clear()
                
            return len(self._memory_store[key])

        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                # 1. Remove entries outside the window
                pipe.zremrangebyscore(key, 0, cutoff)
                # 2. Add current event with a unique ID to prevent collision under burst attacks
                pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
                # 3. Count remaining entries
                pipe.zcard(key)
                # 4. Set TTL to auto-cleanup (window + 60s buffer)
                pipe.expire(key, window_seconds + 60)

                results = await pipe.execute()

            return results[2]  # zcard result

        except Exception as e:
            logger.error(f"[REDIS] Velocity check error: {e}")
            return 0

    async def get_ip_velocity(self, ip: str, window_minutes: int = 15) -> int:
        """Get request count for an IP in the last N minutes."""
        return await self.get_velocity("ip", ip, window_minutes * 60)

    async def get_device_velocity(self, device_hash: str, window_minutes: int = 15) -> int:
        """Get request count for a device hash in the last N minutes."""
        return await self.get_velocity("device", device_hash, window_minutes * 60)

    async def get_pincode_velocity(self, pincode: str, window_minutes: int = 15) -> int:
        """Get request count for a pincode in the last N minutes (Proxy Defense)."""
        return await self.get_velocity("pincode", pincode, window_minutes * 60)

    @property
    def is_connected(self) -> bool:
        return self._connected


# Global singleton
velocity_service = VelocityService()
