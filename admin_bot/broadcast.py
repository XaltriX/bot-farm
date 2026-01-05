import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup

from shared import db, redis_client, BroadcastModel, BroadcastContent, InlineButton
from .utils import generate_broadcast_id

logger = logging.getLogger(__name__)


class BroadcastManager:
    """Manage broadcast operations"""
    
    @staticmethod
    def parse_message_content(message: Message) -> BroadcastContent:
        """Parse message into broadcast content"""
        content_type = "text"
        text = None
        file_id = None
        caption = None
        buttons = []
        
        # Determine content type
        if message.photo:
            content_type = "photo"
            file_id = message.photo[-1].file_id
            caption = message.caption
        elif message.video:
            content_type = "video"
            file_id = message.video.file_id
            caption = message.caption
        elif message.audio:
            content_type = "audio"
            file_id = message.audio.file_id
            caption = message.caption
        elif message.document:
            content_type = "document"
            file_id = message.document.file_id
            caption = message.caption
        elif message.text:
            content_type = "text"
            text = message.text
        
        # Parse inline buttons
        if message.reply_markup and message.reply_markup.inline_keyboard:
            for row in message.reply_markup.inline_keyboard:
                button_row = []
                for button in row:
                    if button.url:
                        button_row.append(InlineButton(text=button.text, url=button.url))
                if button_row:
                    buttons.append(button_row)
        
        return BroadcastContent(
            content_type=content_type,
            text=text,
            file_id=file_id,
            caption=caption,
            buttons=buttons
        )
    
    @staticmethod
    async def create_broadcast(bot_ids: List[str], content: BroadcastContent) -> str:
        """Create a new broadcast"""
        broadcast_id = generate_broadcast_id()
        
        # Count total users
        total_users = 0
        for bot_id in bot_ids:
            count = await db.count_users_by_bot(bot_id)
            total_users += count
        
        # Create broadcast document
        broadcast_data = BroadcastModel(
            broadcast_id=broadcast_id,
            bot_ids=bot_ids,
            content=content,
            total_users=total_users,
            started_at=datetime.utcnow()
        ).model_dump()
        
        # Save to database
        await db.insert_broadcast(broadcast_data)
        
        # Initialize Redis counters
        await redis_client.init_broadcast(broadcast_id)
        
        logger.info(f"Created broadcast {broadcast_id} for {len(bot_ids)} bots, {total_users} users")
        
        return broadcast_id
    
    @staticmethod
    async def get_broadcast_stats(broadcast_id: str) -> Dict[str, Any]:
        """Get broadcast statistics"""
        # Get from Redis
        redis_stats = await redis_client.get_broadcast_stats(broadcast_id)
        
        # Get from MongoDB
        broadcast = await db.get_broadcast(broadcast_id)
        
        if not broadcast:
            return None
        
        return {
            "broadcast_id": broadcast_id,
            "status": redis_stats["status"],
            "current_index": redis_stats["current_index"],
            "sent": redis_stats["sent"],
            "failed": redis_stats["failed"],
            "total_users": broadcast["total_users"],
            "bot_ids": broadcast["bot_ids"]
        }
    
    @staticmethod
    async def pause_broadcast(broadcast_id: str) -> bool:
        """Pause a running broadcast"""
        await redis_client.set_broadcast_status(broadcast_id, "paused")
        await db.update_broadcast_status(broadcast_id, "paused")
        logger.info(f"Paused broadcast {broadcast_id}")
        return True
    
    @staticmethod
    async def resume_broadcast(broadcast_id: str) -> bool:
        """Resume a paused broadcast"""
        await redis_client.set_broadcast_status(broadcast_id, "running")
        await db.update_broadcast_status(broadcast_id, "running")
        logger.info(f"Resumed broadcast {broadcast_id}")
        return True
    
    @staticmethod
    async def cancel_broadcast(broadcast_id: str) -> bool:
        """Cancel a broadcast"""
        await redis_client.set_broadcast_status(broadcast_id, "completed")
        await db.update_broadcast_status(broadcast_id, "completed")
        logger.info(f"Cancelled broadcast {broadcast_id}")
        return True


# Global instance
broadcast_manager = BroadcastManager()