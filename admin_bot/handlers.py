import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler

from shared import db, Crypto, BotModel, BotStatus
from shared.reply_manager import reply_manager
from .utils import (
    is_admin, generate_bot_id, generate_secret_token,
    format_bot_stats
)
from .broadcast import broadcast_manager

logger = logging.getLogger(__name__)

# Conversation states
(WAITING_TOKEN, WAITING_WORKER, WAITING_REPLY, WAITING_BROADCAST_MESSAGE, 
 WAITING_BOT_SELECT, WAITING_REPLY_MESSAGE, WAITING_TEMPLATE_NAME, 
 WAITING_TEMPLATE_DESC, WAITING_TEMPLATE_CONTENT, WAITING_REPLY_MODE,
 WAITING_MULTI_SELECT, WAITING_WORKER_SELECT) = range(12)

# Store temporary data
user_data_store = {}


# ==================== BASIC COMMANDS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    text = (
        "🤖 *Bot Farm Admin Panel v2.0*\n\n"
        "📋 *Bot Management:*\n"
        "/addbot - Add a single bot\n"
        "/bulkupload - Upload .txt file with multiple tokens\n"
        "/listbots - List all bots\n"
        "/stats - Show system statistics\n"
        "/health - Check bot health\n\n"
        "💬 *Reply Management:*\n"
        "/setreply - Set auto-reply (ALL/Multiple/Single)\n"
        "/viewreply - View current replies\n\n"
        "📁 *Templates:*\n"
        "/createtemplate - Create reply template\n"
        "/templates - View all templates\n"
        "/usetemplate - Apply template to bots\n\n"
        "📢 *Broadcasting:*\n"
        "/broadcast - Start a broadcast\n\n"
        "/help - Show this message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ==================== ADD BOT ====================

async def add_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add bot conversation"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🤖 *Add New Bot*\n\n"
        "Please send me the bot token:\n"
        "Format: `123456:ABC-DEF...`",
        parse_mode="Markdown"
    )
    return WAITING_TOKEN


async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive bot token"""
    token = update.message.text.strip()
    
    if ":" not in token:
        await update.message.reply_text("❌ Invalid token format. Please try again:")
        return WAITING_TOKEN
    
    try:
        from telegram import Bot
        test_bot = Bot(token)
        bot_info = await test_bot.get_me()
        
        # Check if already exists
        existing = await db.db.bots.find_one({"bot_username": bot_info.username})
        if existing:
            await update.message.reply_text(
                f"⚠️ Bot @{bot_info.username} already exists!\n\n"
                f"Try another token or /cancel"
            )
            return WAITING_TOKEN
        
        user_data_store[update.effective_user.id] = {
            "token": token,
            "username": bot_info.username
        }
        
        await update.message.reply_text(
            f"✅ Token verified!\n"
            f"Bot: @{bot_info.username}\n\n"
            f"Which worker should handle this bot?\n"
            f"(e.g., `worker-1`, `worker-2`)",
            parse_mode="Markdown"
        )
        return WAITING_WORKER
        
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        await update.message.reply_text(
            f"❌ Token validation failed: {str(e)}\n\n"
            f"Please try again or /cancel"
        )
        return WAITING_TOKEN


async def receive_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive worker assignment"""
    worker_name = update.message.text.strip()
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired. Please start over with /addbot")
        return ConversationHandler.END
    
    data = user_data_store[user_id]
    crypto = Crypto()
    encrypted_token = crypto.encrypt(data["token"])
    
    bot_id = generate_bot_id()
    secret_token = generate_secret_token()
    
    bot_data = BotModel(
        bot_id=bot_id,
        bot_username=data["username"],
        token=encrypted_token,
        secret_token=secret_token,
        assigned_worker=worker_name,
        use_global_reply=True
    ).model_dump()
    
    success = await db.insert_bot(bot_data)
    
    if success:
        await update.message.reply_text(
            f"✅ *Bot Added Successfully!*\n\n"
            f"🤖 Bot: @{data['username']}\n"
            f"🆔 Bot ID: `{bot_id}`\n"
            f"⚙️ Worker: {worker_name}\n"
            f"💬 Reply Mode: Global (uses global reply)\n\n"
            f"The bot will be activated when the worker starts.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Failed to add bot. Please try again.")
    
    del user_data_store[user_id]
    return ConversationHandler.END


# ==================== LIST BOTS ====================

async def list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all bots"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    bots = await db.get_all_bots()
    
    if not bots:
        await update.message.reply_text("No bots found. Add one with /addbot or /bulkupload")
        return
    
    text = f"🤖 *Bot List ({len(bots)} bots)*\n\n"
    
    for bot in bots[:20]:  # Show first 20
        user_count = await db.count_users_by_bot(bot["bot_id"])
        reply_mode = "Custom"
        if bot.get("use_global_reply"):
            reply_mode = "Global"
        elif bot.get("use_worker_reply"):
            reply_mode = "Worker"
        
        status_emoji = "✅" if bot['status'] == "alive" else "❌"
        
        text += f"{status_emoji} @{bot['bot_username']}\n"
        text += f"├ Status: {bot['status']}\n"
        text += f"├ Users: {user_count:,}\n"
        text += f"├ Worker: {bot['assigned_worker']}\n"
        text += f"└ Reply: {reply_mode}\n\n"
    
    if len(bots) > 20:
        text += f"_... and {len(bots) - 20} more bots_"
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ==================== STATS ====================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system statistics"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    bots = await db.get_all_bots()
    templates = await db.get_all_templates()
    
    total_bots = len(bots)
    alive_bots = sum(1 for b in bots if b["status"] == "alive")
    global_reply_bots = sum(1 for b in bots if b.get("use_global_reply", True))
    worker_reply_bots = sum(1 for b in bots if b.get("use_worker_reply") and not b.get("use_global_reply"))
    custom_reply_bots = total_bots - global_reply_bots - worker_reply_bots
    
    total_users = 0
    for bot in bots:
        count = await db.count_users_by_bot(bot["bot_id"])
        total_users += count
    
    # Get worker distribution
    workers = {}
    for bot in bots:
        worker = bot['assigned_worker']
        workers[worker] = workers.get(worker, 0) + 1
    
    text = (
        f"📊 *System Statistics*\n\n"
        f"🤖 *Bots:*\n"
        f"├ Total: {total_bots}\n"
        f"├ Active: {alive_bots}\n"
        f"├ Dead: {total_bots - alive_bots}\n"
        f"├ Global Reply: {global_reply_bots}\n"
        f"├ Worker Reply: {worker_reply_bots}\n"
        f"└ Custom Reply: {custom_reply_bots}\n\n"
        f"👥 *Users:* {total_users:,}\n"
        f"📁 *Templates:* {len(templates)}\n\n"
    )
    
    if workers:
        text += f"⚙️ *Workers:*\n"
        for worker, count in sorted(workers.items()):
            text += f"├ {worker}: {count} bots\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


# ==================== REPLY MANAGEMENT ====================

async def set_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start setting reply - Choose mode"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🌐 ALL Bots", callback_data="reply_mode_all")],
        [InlineKeyboardButton("✅ Select Multiple Bots", callback_data="reply_mode_multi")],
        [InlineKeyboardButton("🎯 Single Bot", callback_data="reply_mode_single")],
        [InlineKeyboardButton("⚙️ By Worker", callback_data="reply_mode_worker")],
    ]
    
    await update.message.reply_text(
        "💬 *Set Auto-Reply*\n\n"
        "Choose how you want to set the reply:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_REPLY_MODE


async def receive_reply_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply mode selection"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.replace("reply_mode_", "")
    user_id = query.from_user.id
    
    user_data_store[user_id] = {"mode": mode}
    
    if mode == "all":
        await query.edit_message_text(
            "🌐 *Set Reply for ALL Bots*\n\n"
            "This will set the same reply for all bots in the system.\n\n"
            "Send me the reply message now:\n"
            "• Plain text\n"
            "• Text with buttons: `[Button Text](https://url.com)`\n"
            "• Photo/Video with caption\n\n"
            "*Variables you can use:*\n"
            "`{user_name}` - User's first name\n"
            "`{user_id}` - User's ID\n"
            "`{bot_name}` - Bot's name\n"
            "`{bot_username}` - Bot's username",
            parse_mode="Markdown"
        )
        return WAITING_REPLY_MESSAGE
    
    elif mode == "worker":
        # Get unique workers
        bots = await db.get_all_bots()
        workers = sorted(list(set(b["assigned_worker"] for b in bots)))
        
        if not workers:
            await query.edit_message_text("❌ No workers found. Add bots first!")
            return ConversationHandler.END
        
        keyboard = [[InlineKeyboardButton(w, callback_data=f"worker_{w}")] for w in workers]
        
        await query.edit_message_text(
            "⚙️ *Select Worker*\n\n"
            "Choose which worker's bots should get this reply:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return WAITING_WORKER_SELECT
    
    elif mode == "multi":
        bots = await db.get_all_bots()
        if not bots:
            await query.edit_message_text("❌ No bots found. Add bots first!")
            return ConversationHandler.END
        
        # Show bot selection with pagination
        keyboard = []
        for bot in bots[:10]:  # Show first 10
            keyboard.append([InlineKeyboardButton(
                f"☐ @{bot['bot_username']}", 
                callback_data=f"togglebot_{bot['bot_id']}"
            )])
        keyboard.append([InlineKeyboardButton("✅ Done Selecting", callback_data="multi_done")])
        
        user_data_store[user_id]["selected_bots"] = []
        
        await query.edit_message_text(
            "✅ *Select Multiple Bots*\n\n"
            "Tap bots to select/deselect:\n"
            "(Showing first 10 bots)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return WAITING_MULTI_SELECT
    
    else:  # single
        bots = await db.get_all_bots()
        if not bots:
            await query.edit_message_text("❌ No bots found. Add bots first!")
            return ConversationHandler.END
        
        keyboard = [[InlineKeyboardButton(
            f"@{bot['bot_username']}", 
            callback_data=f"singlebot_{bot['bot_id']}"
        )] for bot in bots[:15]]
        
        await query.edit_message_text(
            "🎯 *Select Bot*\n\n"
            "Choose which bot to set reply for:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return WAITING_BOT_SELECT


async def receive_worker_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle worker selection"""
    query = update.callback_query
    await query.answer()
    
    worker_name = query.data.replace("worker_", "")
    user_id = query.from_user.id
    
    user_data_store[user_id]["worker"] = worker_name
    
    await query.edit_message_text(
        f"⚙️ *Setting Reply for Worker: {worker_name}*\n\n"
        f"Send me the reply message now:\n"
        f"• Plain text\n"
        f"• Text with buttons: `[Button Text](https://url.com)`\n"
        f"• Photo/Video with caption\n\n"
        f"*Variables:* `{{user_name}}`, `{{user_id}}`, `{{bot_name}}`",
        parse_mode="Markdown"
    )
    
    return WAITING_REPLY_MESSAGE


async def toggle_bot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle bot selection in multi-select mode"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "multi_done":
        await query.answer()
        
        if user_id not in user_data_store or not user_data_store[user_id].get("selected_bots"):
            await query.answer("❌ Please select at least one bot!", show_alert=True)
            return WAITING_MULTI_SELECT
        
        count = len(user_data_store[user_id]["selected_bots"])
        await query.edit_message_text(
            f"✅ *{count} Bots Selected*\n\n"
            f"Now send me the reply message:\n"
            f"• Plain text\n"
            f"• Text with buttons: `[Button Text](https://url.com)`\n"
            f"• Photo/Video with caption\n\n"
            f"*Variables:* `{{user_name}}`, `{{user_id}}`, `{{bot_name}}`",
            parse_mode="Markdown"
        )
        return WAITING_REPLY_MESSAGE
    
    bot_id = query.data.replace("togglebot_", "")
    
    if user_id not in user_data_store:
        user_data_store[user_id] = {"selected_bots": []}
    
    selected = user_data_store[user_id].get("selected_bots", [])
    
    if bot_id in selected:
        selected.remove(bot_id)
        await query.answer("❌ Deselected")
    else:
        selected.append(bot_id)
        await query.answer("✅ Selected")
    
    user_data_store[user_id]["selected_bots"] = selected
    
    # Update keyboard
    bots = await db.get_all_bots()
    keyboard = []
    for bot in bots[:10]:
        check = "☑" if bot["bot_id"] in selected else "☐"
        keyboard.append([InlineKeyboardButton(
            f"{check} @{bot['bot_username']}", 
            callback_data=f"togglebot_{bot['bot_id']}"
        )])
    keyboard.append([InlineKeyboardButton(f"✅ Done ({len(selected)} selected)", callback_data="multi_done")])
    
    await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
    
    return WAITING_MULTI_SELECT


async def receive_single_bot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle single bot selection"""
    query = update.callback_query
    await query.answer()
    
    bot_id = query.data.replace("singlebot_", "")
    user_id = query.from_user.id
    
    bot_data = await db.get_bot(bot_id)
    if not bot_data:
        await query.edit_message_text("❌ Bot not found!")
        return ConversationHandler.END
    
    user_data_store[user_id]["bot_id"] = bot_id
    
    await query.edit_message_text(
        f"🎯 *Setting Reply for @{bot_data['bot_username']}*\n\n"
        f"Send me the reply message:\n"
        f"• Plain text\n"
        f"• Text with buttons: `[Button Text](https://url.com)`\n"
        f"• Photo/Video with caption\n\n"
        f"*Variables:* `{{user_name}}`, `{{user_id}}`, `{{bot_name}}`",
        parse_mode="Markdown"
    )
    
    return WAITING_REPLY_MESSAGE


async def receive_reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save reply message"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired. Start over with /setreply")
        return ConversationHandler.END
    
    data = user_data_store[user_id]
    mode = data.get("mode")
    
    # Parse message
    reply_content = reply_manager.parse_message_to_reply(update.message)
    
    if mode == "all":
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
                "✅ *Global Reply Set!*\n\n"
                "All bots will now use this reply (unless they have custom/worker reply).\n\n"
                "*Preview:*",
                parse_mode="Markdown"
            )
            
            await update.message.reply_text(
                reply_content.get("text", "Hello!"),
                reply_markup=preview_keyboard
            )
        else:
            await update.message.reply_text("❌ Failed to set global reply.")
    
    elif mode == "worker":
        worker_name = data.get("worker")
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
    
    elif mode == "multi":
        selected_bots = data.get("selected_bots", [])
        count = await db.update_bots_reply(selected_bots, reply_content)
        
        await update.message.reply_text(
            f"✅ *Reply Set for {count} Bots!*\n\n"
            f"Selected bots will now use this custom reply.",
            parse_mode="Markdown"
        )
    
    else:  # single
        bot_id = data.get("bot_id")
        result = await db.db.bots.update_one(
            {"bot_id": bot_id},
            {"$set": {"auto_reply": reply_content, "use_global_reply": False, "use_worker_reply": False}}
        )
        
        if result.modified_count > 0:
            await update.message.reply_text(
                "✅ *Reply Set!*\n\n"
                "Bot will now use this custom reply.",
                parse_mode="Markdown"
            )
    
    del user_data_store[user_id]
    return ConversationHandler.END


async def view_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View current auto-reply settings"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    # Show global reply
    global_reply = await db.get_global_reply()
    
    text = "💬 *Reply Configuration*\n\n"
    
    if global_reply and global_reply.get("enabled"):
        content = global_reply.get("content", {})
        text += f"🌐 *Global Reply:* ✅ Enabled\n"
        text += f"Text: {content.get('text', 'N/A')[:50]}...\n\n"
    else:
        text += f"🌐 *Global Reply:* ❌ Not set\n\n"
    
    # Show sample of bot replies
    bots = await db.get_all_bots()
    if bots:
        global_count = sum(1 for b in bots if b.get("use_global_reply", True))
        worker_count = sum(1 for b in bots if b.get("use_worker_reply") and not b.get("use_global_reply"))
        custom_count = len(bots) - global_count - worker_count
        
        text += f"📊 *Bot Distribution:*\n"
        text += f"├ Using Global: {global_count}\n"
        text += f"├ Using Worker: {worker_count}\n"
        text += f"└ Custom Reply: {custom_count}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def global_reply_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick set global reply"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    await update.message.reply_text(
        "🌐 *Set Global Reply*\n\n"
        "This will be used by ALL bots (unless they have custom reply).\n\n"
        "Send your message now:\n"
        "• Plain text\n"
        "• Text with buttons: `[Button](https://url.com)`\n"
        "• Photo/Video with caption\n\n"
        "*Variables:* `{user_name}`, `{user_id}`, `{bot_name}`",
        parse_mode="Markdown"
    )


# ==================== CANCEL ====================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END