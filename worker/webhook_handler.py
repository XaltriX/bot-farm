import logging
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from shared import db, Crypto
from shared.reply_manager import reply_manager

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handle incoming webhook requests from child bots"""
    
    def __init__(self):
        self.crypto = Crypto()
        self.bots_cache = {}  # Cache bot instances
    
    async def load_bot(self, bot_id: str) -> Bot:
        """Load bot instance from cache or database"""
        if bot_id in self.bots_cache:
            return self.bots_cache[bot_id]
        
        # Load from database
        bot_data = await db.get_bot(bot_id)
        if not bot_data:
            logger.error(f"Bot {bot_id} not found in database")
            return None
        
        # Decrypt token
        token = self.crypto.decrypt(bot_data["token"])
        bot = Bot(token)
        
        # Cache it
        self.bots_cache[bot_id] = bot
        
        return bot
    
    async def verify_secret(self, bot_id: str, received_secret: str) -> bool:
        """Verify webhook secret token"""
        bot_data = await db.get_bot(bot_id)
        if not bot_data:
            return False
        
        return bot_data["secret_token"] == received_secret
    
    async def handle_message(self, bot_id: str, update_data: dict):
        """Handle incoming message from user"""
        try:
            # Parse update
            update = Update.de_json(update_data, None)
            
            if not update.message:
                return
            
            user = update.message.from_user
            user_id = user.id
            
            # Prepare user data for variable replacement
            user_data = {
                "user_id": user_id,
                "first_name": user.first_name or "User",
                "username": user.username or "User"
            }
            
            # Save/update user with more info
            await db.db.users.update_one(
                {"user_id": user_id, "bot_id": bot_id},
                {
                    "$set": {
                        "last_seen": update.message.date,
                        "first_name": user.first_name,
                        "username": user.username
                    },
                    "$setOnInsert": {"first_seen": update.message.date},
                    "$inc": {"message_count": 1}
                },
                upsert=True
            )
            
            # Load bot
            bot = await self.load_bot(bot_id)
            if not bot:
                logger.error(f"Failed to load bot {bot_id}")
                return
            
            # Get bot data for variables
            bot_data = await db.get_bot(bot_id)
            
            # Get appropriate reply using priority system
            reply_content = await reply_manager.get_reply_for_bot(db, bot_id)
            
            if not reply_content:
                # Fallback to default
                await bot.send_message(
                    chat_id=user_id,
                    text="Hello! 👋"
                )
                return
            
            # Prepare text with variables
            text = reply_manager.prepare_reply_text(reply_content, user_data, bot_data)
            
            # Build inline keyboard if buttons exist
            keyboard = None
            if reply_content.get("buttons"):
                keyboard_buttons = []
                for row in reply_content["buttons"]:
                    button_row = [
                        InlineKeyboardButton(text=btn["text"], url=btn["url"])
                        for btn in row
                    ]
                    keyboard_buttons.append(button_row)
                keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Send based on media type
            media_type = reply_content.get("media_type")
            
            if media_type == "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=reply_content["media_file_id"],
                    caption=text,
                    reply_markup=keyboard
                )
            elif media_type == "video":
                await bot.send_video(
                    chat_id=user_id,
                    video=reply_content["media_file_id"],
                    caption=text,
                    reply_markup=keyboard
                )
            elif media_type == "document":
                await bot.send_document(
                    chat_id=user_id,
                    document=reply_content["media_file_id"],
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                # Text message
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=keyboard
                )
            
            logger.info(f"Handled message from {user_id} on bot {bot_id}")
            
        except Exception as e:
            logger.error(f"Error handling message for bot {bot_id}: {e}")
    
    def clear_cache(self, bot_id: str = None):
        """Clear bot cache"""
        if bot_id:
            self.bots_cache.pop(bot_id, None)
        else:
            self.bots_cache.clear()


# Global handler instance
webhook_handler: WebhookHandler | None = None

def get_webhook_handler() -> WebhookHandler:
    global webhook_handler
    if webhook_handler is None:
        webhook_handler = WebhookHandler()
    return webhook_handler
