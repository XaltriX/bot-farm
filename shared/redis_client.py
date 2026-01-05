import os
import redis.asyncio as aioredis
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis connection handler for broadcast state"""
    
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        password = os.getenv("REDIS_PASSWORD", None)
        
        self.client = await aioredis.from_url(
            f"redis://{host}:{port}",
            password=password,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info(f"Connected to Redis: {host}:{port}")
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")
    
    # Broadcast state operations
    async def set_broadcast_index(self, broadcast_id: str, index: int):
        """Set current broadcast index"""
        await self.client.set(f"broadcast:{broadcast_id}:current_index", index)
    
    async def get_broadcast_index(self, broadcast_id: str) -> int:
        """Get current broadcast index"""
        value = await self.client.get(f"broadcast:{broadcast_id}:current_index")
        return int(value) if value else 0
    
    async def increment_sent(self, broadcast_id: str) -> int:
        """Increment sent counter"""
        return await self.client.incr(f"broadcast:{broadcast_id}:sent")
    
    async def increment_failed(self, broadcast_id: str) -> int:
        """Increment failed counter"""
        return await self.client.incr(f"broadcast:{broadcast_id}:failed")
    
    async def get_broadcast_stats(self, broadcast_id: str) -> dict:
        """Get all broadcast stats"""
        pipe = self.client.pipeline()
        pipe.get(f"broadcast:{broadcast_id}:current_index")
        pipe.get(f"broadcast:{broadcast_id}:sent")
        pipe.get(f"broadcast:{broadcast_id}:failed")
        pipe.get(f"broadcast:{broadcast_id}:status")
        
        results = await pipe.execute()
        
        return {
            "current_index": int(results[0]) if results[0] else 0,
            "sent": int(results[1]) if results[1] else 0,
            "failed": int(results[2]) if results[2] else 0,
            "status": results[3] if results[3] else "unknown"
        }
    
    async def set_broadcast_status(self, broadcast_id: str, status: str):
        """Set broadcast status"""
        await self.client.set(f"broadcast:{broadcast_id}:status", status)
    
    async def get_broadcast_status(self, broadcast_id: str) -> str:
        """Get broadcast status"""
        status = await self.client.get(f"broadcast:{broadcast_id}:status")
        return status if status else "unknown"
    
    async def delete_broadcast_data(self, broadcast_id: str):
        """Delete all broadcast data"""
        keys = [
            f"broadcast:{broadcast_id}:current_index",
            f"broadcast:{broadcast_id}:sent",
            f"broadcast:{broadcast_id}:failed",
            f"broadcast:{broadcast_id}:status"
        ]
        await self.client.delete(*keys)
    
    async def init_broadcast(self, broadcast_id: str):
        """Initialize broadcast counters"""
        pipe = self.client.pipeline()
        pipe.set(f"broadcast:{broadcast_id}:current_index", 0)
        pipe.set(f"broadcast:{broadcast_id}:sent", 0)
        pipe.set(f"broadcast:{broadcast_id}:failed", 0)
        pipe.set(f"broadcast:{broadcast_id}:status", "running")
        await pipe.execute()
    
    # Bot file_id cache
    async def set_file_id(self, bot_id: str, file_key: str, file_id: str):
        """Cache file_id for a bot"""
        await self.client.set(f"bot:{bot_id}:file:{file_key}", file_id, ex=86400 * 30)
    
    async def get_file_id(self, bot_id: str, file_key: str) -> Optional[str]:
        """Get cached file_id"""
        return await self.client.get(f"bot:{bot_id}:file:{file_key}")


# Global Redis instance
redis_client = RedisClient()