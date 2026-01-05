import asyncio
import logging
from typing import Dict, List
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError

from shared import db, redis_client, Crypto

logger = logging.getLogger(__name__)


class BroadcastEngine:
    """Handle broadcast message sending"""
    
    def __init__(self, worker_name: str, messages_per_second: int = 15):
        self.worker_name = worker_name
        self.messages_per_second = messages_per_second
        self.delay = 1.0 / messages_per_second
        self.crypto = Crypto()
        self.bots_cache: Dict[str, Bot] = {}
        self.active_broadcasts = set()
        self.file_cache: Dict[str, Dict[str, str]] = {}  # {bot_id: {file_key: file_id}}
    
    async def load_bot(self, bot_id: str) -> Bot:
        """Load bot instance"""
        if bot_id in self.bots_cache:
            return self.bots_cache[bot_id]
        
        bot_data = await db.get_bot(bot_id)
        if not bot_data:
            return None
        
        token = self.crypto.decrypt(bot_data["token"])
        bot = Bot(token)
        self.bots_cache[bot_id] = bot
        
        return bot
    
    async def send_broadcast_message(
        self,
        bot: Bot,
        bot_id: str,
        user_id: int,
        content: dict
    ) -> bool:
        """Send a single broadcast message"""
        try:
            content_type = content["content_type"]
            
            # Build inline keyboard
            keyboard = None
            if content.get("buttons"):
                keyboard_buttons = []
                for row in content["buttons"]:
                    button_row = [
                        InlineKeyboardButton(text=btn["text"], url=btn["url"])
                        for btn in row
                    ]
                    keyboard_buttons.append(button_row)
                keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Send based on content type
            if content_type == "text":
                await bot.send_message(
                    chat_id=user_id,
                    text=content["text"],
                    reply_markup=keyboard
                )
            
            elif content_type == "photo":
                # Try cached file_id first
                file_id = await self.get_cached_file_id(bot_id, content.get("file_id"))
                
                try:
                    result = await bot.send_photo(
                        chat_id=user_id,
                        photo=file_id,
                        caption=content.get("caption"),
                        reply_markup=keyboard
                    )
                    # Cache the file_id
                    await self.cache_file_id(bot_id, content.get("file_id"), result.photo[-1].file_id)
                except TelegramError:
                    # File not found, use original
                    result = await bot.send_photo(
                        chat_id=user_id,
                        photo=content["file_id"],
                        caption=content.get("caption"),
                        reply_markup=keyboard
                    )
                    await self.cache_file_id(bot_id, content.get("file_id"), result.photo[-1].file_id)
            
            elif content_type == "video":
                file_id = await self.get_cached_file_id(bot_id, content.get("file_id"))
                try:
                    result = await bot.send_video(
                        chat_id=user_id,
                        video=file_id,
                        caption=content.get("caption"),
                        reply_markup=keyboard
                    )
                    await self.cache_file_id(bot_id, content.get("file_id"), result.video.file_id)
                except TelegramError:
                    result = await bot.send_video(
                        chat_id=user_id,
                        video=content["file_id"],
                        caption=content.get("caption"),
                        reply_markup=keyboard
                    )
                    await self.cache_file_id(bot_id, content.get("file_id"), result.video.file_id)
            
            elif content_type == "audio":
                file_id = await self.get_cached_file_id(bot_id, content.get("file_id"))
                await bot.send_audio(
                    chat_id=user_id,
                    audio=file_id,
                    caption=content.get("caption"),
                    reply_markup=keyboard
                )
            
            elif content_type == "document":
                file_id = await self.get_cached_file_id(bot_id, content.get("file_id"))
                await bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=content.get("caption"),
                    reply_markup=keyboard
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending to {user_id} via {bot_id}: {e}")
            return False
    
    async def get_cached_file_id(self, bot_id: str, original_file_id: str) -> str:
        """Get cached file_id from Redis"""
        cached = await redis_client.get_file_id(bot_id, original_file_id)
        return cached if cached else original_file_id
    
    async def cache_file_id(self, bot_id: str, original_file_id: str, new_file_id: str):
        """Cache file_id in Redis"""
        await redis_client.set_file_id(bot_id, original_file_id, new_file_id)
    
    async def process_broadcast(self, broadcast_id: str):
        """Process a single broadcast"""
        if broadcast_id in self.active_broadcasts:
            logger.warning(f"Broadcast {broadcast_id} already active")
            return
        
        self.active_broadcasts.add(broadcast_id)
        
        try:
            # Get broadcast data
            broadcast = await db.get_broadcast(broadcast_id)
            if not broadcast:
                logger.error(f"Broadcast {broadcast_id} not found")
                return
            
            # Filter bots assigned to this worker
            my_bots = []
            for bot_id in broadcast["bot_ids"]:
                bot_data = await db.get_bot(bot_id)
                if bot_data and bot_data["assigned_worker"] == self.worker_name:
                    my_bots.append(bot_data)
            
            if not my_bots:
                logger.info(f"No bots for this worker in broadcast {broadcast_id}")
                return
            
            logger.info(f"Processing broadcast {broadcast_id} with {len(my_bots)} bots")
            
            # Process each bot's users
            for bot_data in my_bots:
                bot_id = bot_data["bot_id"]
                
                # Check if broadcast is paused
                status = await redis_client.get_broadcast_status(broadcast_id)
                if status == "paused":
                    logger.info(f"Broadcast {broadcast_id} paused")
                    break
                
                if status == "completed":
                    logger.info(f"Broadcast {broadcast_id} completed")
                    break
                
                # Load bot
                bot = await self.load_bot(bot_id)
                if not bot:
                    continue
                
                # Get users for this bot
                users = []
                async for user in db.get_all_users_for_bots([bot_id]):
                    users.append(user)
                
                logger.info(f"Bot {bot_id}: {len(users)} users")
                
                # Send to each user
                for user in users:
                    # Check pause status
                    status = await redis_client.get_broadcast_status(broadcast_id)
                    if status in ["paused", "completed"]:
                        break
                    
                    # Send message
                    success = await self.send_broadcast_message(
                        bot,
                        bot_id,
                        user["user_id"],
                        broadcast["content"]
                    )
                    
                    # Update counters
                    if success:
                        await redis_client.increment_sent(broadcast_id)
                    else:
                        await redis_client.increment_failed(broadcast_id)
                    
                    # Rate limiting
                    await asyncio.sleep(self.delay)
            
            # Mark as completed
            await redis_client.set_broadcast_status(broadcast_id, "completed")
            await db.update_broadcast_status(broadcast_id, "completed")
            
            # Update final stats
            stats = await redis_client.get_broadcast_stats(broadcast_id)
            await db.update_broadcast_stats(
                broadcast_id,
                stats["sent"],
                stats["failed"]
            )
            
            logger.info(f"Broadcast {broadcast_id} completed")
            
        except Exception as e:
            logger.error(f"Error processing broadcast {broadcast_id}: {e}")
        finally:
            self.active_broadcasts.discard(broadcast_id)
    
    async def monitor_broadcasts(self):
        """Monitor for new broadcasts"""
        logger.info("Broadcast monitor started")
        
        while True:
            try:
                # Check for running broadcasts
                broadcasts = await db.db.broadcasts.find(
                    {"status": "running"}
                ).to_list(length=None)
                
                for broadcast in broadcasts:
                    broadcast_id = broadcast["broadcast_id"]
                    
                    # Skip if already processing
                    if broadcast_id in self.active_broadcasts:
                        continue
                    
                    # Start processing in background
                    asyncio.create_task(self.process_broadcast(broadcast_id))
                
                # Check every 10 seconds
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in broadcast monitor: {e}")
                await asyncio.sleep(10)


# Global instance
broadcast_engine = None


def get_broadcast_engine(worker_name: str) -> BroadcastEngine:
    """Get or create broadcast engine"""
    global broadcast_engine
    if broadcast_engine is None:
        broadcast_engine = BroadcastEngine(worker_name)
    return broadcast_engine