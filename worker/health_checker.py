import asyncio
import logging
from telegram import Bot
from shared import db, Crypto

logger = logging.getLogger(__name__)


class HealthChecker:
    """Periodically check bot token health"""
    
    def __init__(self, worker_name: str, check_interval: int = 3600):
        self.worker_name = worker_name
        self.check_interval = check_interval  # seconds
        self.crypto = Crypto()
    
    async def check_bot(self, bot_data: dict) -> bool:
        """Check if a single bot is alive"""
        try:
            token = self.crypto.decrypt(bot_data["token"])
            bot = Bot(token)
            await bot.get_me()
            return True
        except Exception as e:
            logger.error(f"Bot {bot_data['bot_id']} health check failed: {e}")
            return False
    
    async def check_all_bots(self):
        """Check health of all bots assigned to this worker"""
        logger.info(f"Starting health check for worker {self.worker_name}")
        
        try:
            # Get bots for this worker
            bots = await db.get_bots_by_worker(self.worker_name)
            
            results = {"alive": 0, "dead": 0}
            
            for bot_data in bots:
                is_alive = await self.check_bot(bot_data)
                
                if is_alive:
                    await db.update_bot_status(bot_data["bot_id"], "alive")
                    results["alive"] += 1
                else:
                    await db.update_bot_status(bot_data["bot_id"], "dead")
                    results["dead"] += 1
                
                # Small delay between checks
                await asyncio.sleep(0.1)
            
            logger.info(
                f"Health check completed: {results['alive']} alive, "
                f"{results['dead']} dead"
            )
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
    
    async def start_monitoring(self):
        """Start periodic health monitoring"""
        logger.info(
            f"Health monitoring started (interval: {self.check_interval}s)"
        )
        
        while True:
            try:
                await self.check_all_bots()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(60)


# Global instance
health_checker = None


def get_health_checker(worker_name: str) -> HealthChecker:
    """Get or create health checker"""
    global health_checker
    if health_checker is None:
        health_checker = HealthChecker(worker_name)
    return health_checker