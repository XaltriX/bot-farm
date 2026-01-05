"""Quick reply shortcuts - globalreply and workerreply"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from shared import db
from shared.reply_manager import reply_manager
from .handlers import is_admin, user_data_store

logger = logging.getLogger(__name__)

WAITING_GLOBAL_MESSAGE, WAITING_WORKER_NAME, WAITING_WORKER_MESSAGE = range(200, 203)


# ==================== GLOBAL REPLY ====================

async def global_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start global reply setup"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🌐 *Set Global Reply*\n\n"
        "This will be used by ALL bots (unless they have custom reply).\n\n"
        "Send your message now:\n"
        "• Plain text\n"
        "• Text with buttons: `[Button](https://url.com)`\n"
        "• Photo/Video with caption\n\n"
        "*Variables:* `{user_name}`, `{user_id}`, `{bot_name}`\n\n"
        "Example:\n"
        "```\n"
        "Welcome {user_name}! 👋\n\n"
        "[Visit Website](https://example.com)\n"
        "[Join Channel](https://t.me/channel)\n"
        "```",
        parse_mode="Markdown"
    )
    
    return WAITING_GLOBAL_MESSAGE


async def receive_global_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save global reply"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return ConversationHandler.END
    
    # Parse message
    reply_content = reply_manager.parse_message_to_reply(update.message)
    
    if not reply_content.get("text") and not reply_content.get("media_file_id"):
        await update.message.reply_text("❌ Message cannot be empty!")
        return WAITING_GLOBAL_MESSAGE
    
    # Set global reply
    global_reply = {
        "reply_id": "global_default",
        "content": reply_content,
        "enabled": True
    }
    
    success = await db.set_global_reply(global_reply)
    
    if success:
        # Preview
        preview_keyboard = None
        if reply_content.get("buttons"):
            keyboard_buttons = []
            for row in reply_content["buttons"]:
                button_row = [InlineKeyboardButton(text=btn["text"], url=btn["url"]) for btn in row]
                keyboard_buttons.append(button_row)
            preview_keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await update.message.reply_text(
            "✅ *Global Reply Set Successfully!*\n\n"
            "All bots will now use this reply.\n\n"
            "*Preview:*",
            parse_mode="Markdown"
        )
        
        # Send preview
        text = reply_content.get("text", "Hello!")
        if reply_content.get("media_type") == "photo":
            await update.message.reply_photo(
                photo=reply_content["media_file_id"],
                caption=text,
                reply_markup=preview_keyboard
            )
        elif reply_content.get("media_type") == "video":
            await update.message.reply_video(
                video=reply_content["media_file_id"],
                caption=text,
                reply_markup=preview_keyboard
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=preview_keyboard
            )
    else:
        await update.message.reply_text("❌ Failed to set global reply.")
    
    return ConversationHandler.END


# ==================== WORKER REPLY ====================

async def worker_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start worker reply setup"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    # Get unique workers
    bots = await db.get_all_bots()
    workers = sorted(list(set(b["assigned_worker"] for b in bots)))
    
    if not workers:
        await update.message.reply_text("❌ No workers found. Add bots first!")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(w, callback_data=f"wreply_{w}")] for w in workers]
    
    await update.message.reply_text(
        "⚙️ *Set Worker Reply*\n\n"
        "Select which worker:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_WORKER_NAME


async def receive_worker_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle worker selection"""
    query = update.callback_query
    await query.answer()
    
    worker_name = query.data.replace("wreply_", "")
    user_id = query.from_user.id
    
    user_data_store[user_id] = {"worker": worker_name}
    
    await query.edit_message_text(
        f"⚙️ *Setting Reply for Worker: {worker_name}*\n\n"
        f"Send your message now:\n"
        f"• Plain text\n"
        f"• Text with buttons: `[Button](https://url.com)`\n"
        f"• Photo/Video with caption\n\n"
        f"*Variables:* `{{user_name}}`, `{{user_id}}`, `{{bot_name}}`",
        parse_mode="Markdown"
    )
    
    return WAITING_WORKER_MESSAGE


async def receive_worker_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save worker reply"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    
    worker_name = user_data_store[user_id]["worker"]
    
    # Parse message
    reply_content = reply_manager.parse_message_to_reply(update.message)
    
    worker_reply = {
        "content": reply_content,
        "enabled": True
    }
    
    success = await db.set_worker_reply(worker_name, worker_reply)
    
    if success:
        await update.message.reply_text(
            f"✅ *Worker Reply Set!*\n\n"
            f"All bots in `{worker_name}` will use this reply.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Failed to set worker reply.")
    
    del user_data_store[user_id]
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END