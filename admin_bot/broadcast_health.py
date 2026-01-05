"""Broadcast and Health Check Handlers"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from shared import db, Crypto
from .broadcast import broadcast_manager
from .handlers import is_admin, user_data_store

logger = logging.getLogger(__name__)

WAITING_BROADCAST_MESSAGE = 20


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    bots = await db.get_all_bots()
    alive_bots = [b for b in bots if b["status"] == "alive"]
    
    if not alive_bots:
        await update.message.reply_text("❌ No active bots available for broadcast.")
        return ConversationHandler.END
    
    # Count total users
    total_users = 0
    for bot in alive_bots:
        count = await db.count_users_by_bot(bot["bot_id"])
        total_users += count
    
    # Store bot IDs
    bot_ids = [b["bot_id"] for b in alive_bots]
    user_data_store[update.effective_user.id] = {"bot_ids": bot_ids}
    
    await update.message.reply_text(
        f"📢 *Start Broadcast*\n\n"
        f"Broadcasting to:\n"
        f"├ Bots: {len(bot_ids)}\n"
        f"└ Users: {total_users:,}\n\n"
        f"Please reply to this message with your broadcast content:\n"
        f"• Text message\n"
        f"• Photo/Video/Audio/Document with caption\n"
        f"• You can add inline buttons\n\n"
        f"*Variables:* `{{user_name}}`, `{{user_id}}`, `{{bot_name}}`",
        parse_mode="Markdown"
    )
    return WAITING_BROADCAST_MESSAGE


async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive broadcast message"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired. Please start over with /broadcast")
        return ConversationHandler.END
    
    data = user_data_store[user_id]
    
    # Parse message content
    content = broadcast_manager.parse_message_content(update.message)
    
    # Create broadcast
    broadcast_id = await broadcast_manager.create_broadcast(data["bot_ids"], content)
    
    await update.message.reply_text(
        f"✅ *Broadcast Created!*\n\n"
        f"Broadcast ID: `{broadcast_id}`\n"
        f"Bots: {len(data['bot_ids'])}\n\n"
        f"Workers will start processing shortly.\n\n"
        f"Use /broadcaststats `{broadcast_id}` to check progress.",
        parse_mode="Markdown"
    )
    
    # Cleanup
    del user_data_store[user_id]
    
    return ConversationHandler.END


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual health check"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    await update.message.reply_text("🔄 Starting health check...")
    
    bots = await db.get_all_bots()
    crypto = Crypto()
    
    results = {"alive": 0, "dead": 0}
    
    for bot in bots:
        try:
            from telegram import Bot
            token = crypto.decrypt(bot["token"])
            test_bot = Bot(token)
            await test_bot.get_me()
            
            await db.update_bot_status(bot["bot_id"], "alive")
            results["alive"] += 1
        except:
            await db.update_bot_status(bot["bot_id"], "dead")
            results["dead"] += 1
    
    await update.message.reply_text(
        f"✅ *Health Check Completed!*\n\n"
        f"✅ Alive: {results['alive']}\n"
        f"❌ Dead: {results['dead']}",
        parse_mode="Markdown"
    )