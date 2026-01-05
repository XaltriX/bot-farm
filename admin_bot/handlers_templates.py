"""Template Management Handlers"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from shared import db
from shared.reply_manager import reply_manager
from .handlers import is_admin, user_data_store

logger = logging.getLogger(__name__)

# States
WAITING_TEMPLATE_NAME, WAITING_TEMPLATE_DESC, WAITING_TEMPLATE_CONTENT = range(10, 13)
WAITING_TEMPLATE_SELECT, WAITING_TEMPLATE_MODE = range(13, 15)


async def create_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a template"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📁 <b>Create Reply Template</b>\n\n"
        "Step 1: Give your template a name\n"
        "Example: <code>Welcome Template</code>, <code>Promo 2024</code>, <code>Support Message</code>",
        parse_mode="HTML"
    )
    
    return WAITING_TEMPLATE_NAME


async def receive_template_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive template name"""
    template_name = update.message.text.strip()
    user_id = update.effective_user.id
    
    user_data_store[user_id] = {"template_name": template_name}
    
    await update.message.reply_text(
        f"✅ Template name: <b>{template_name}</b>\n\n"
        f"Step 2: Send a short description (optional)\n"
        f"Or send <code>/skip</code> to skip",
        parse_mode="HTML"
    )
    
    return WAITING_TEMPLATE_DESC


async def receive_template_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive template description"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    
    if update.message.text.strip() == "/skip":
        description = None
    else:
        description = update.message.text.strip()
    
    user_data_store[user_id]["template_desc"] = description
    
    await update.message.reply_text(
        "📝 <b>Step 3: Send the template content</b>\n\n"
        "Send the message you want to save as template:\n"
        "• Plain text\n"
        "• Text with buttons: <code>[Button](https://url.com)</code>\n"
        "• Photo/Video with caption\n\n"
        "<b>Variables:</b> <code>{user_name}</code>, <code>{user_id}</code>, <code>{bot_name}</code>",
        parse_mode="HTML"
    )
    
    return WAITING_TEMPLATE_CONTENT


async def receive_template_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save template content"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    
    data = user_data_store[user_id]
    
    # Parse message
    reply_content = reply_manager.parse_message_to_reply(update.message)
    
    # Create template
    import uuid
    template_id = f"tpl_{uuid.uuid4().hex[:12]}"
    
    template_data = {
        "template_id": template_id,
        "name": data["template_name"],
        "description": data.get("template_desc"),
        "content": reply_content,
        "usage_count": 0
    }
    
    success = await db.insert_template(template_data)
    
    if success:
        # Show preview
        text = reply_content.get("text", "")
        keyboard = None
        
        if reply_content.get("buttons"):
            keyboard_buttons = []
            for row in reply_content["buttons"]:
                button_row = [InlineKeyboardButton(text=btn["text"], url=btn["url"]) for btn in row]
                keyboard_buttons.append(button_row)
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Escape HTML special characters in text preview
        text_preview = text[:100].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        template_name_escaped = data['template_name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        await update.message.reply_text(
            f"✅ <b>Template Created!</b>\n\n"
            f"Name: {template_name_escaped}\n"
            f"ID: <code>{template_id}</code>\n\n"
            f"Preview:\n{text_preview}{'...' if len(text) > 100 else ''}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Failed to create template.")
    
    del user_data_store[user_id]
    return ConversationHandler.END


async def list_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all templates"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    templates = await db.get_all_templates()
    
    if not templates:
        await update.message.reply_text(
            "📁 No templates found.\n\n"
            "Create one with /createtemplate"
        )
        return
    
    text = f"📁 <b>Templates ({len(templates)})</b>\n\n"
    
    for tpl in templates:
        content = tpl.get("content", {})
        # Escape HTML in template name
        name = tpl['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text += f"<b>{name}</b>\n"
        text += f"├ ID: <code>{tpl['template_id']}</code>\n"
        text += f"├ Used: {tpl.get('usage_count', 0)} times\n"
        
        if tpl.get("description"):
            desc = tpl['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            text += f"├ Desc: {desc}\n"
        
        preview = content.get("text", "")[:40].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text += f"└ Preview: {preview}...\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML")


async def use_template_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start using a template"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    templates = await db.get_all_templates()
    
    if not templates:
        await update.message.reply_text(
            "📁 No templates available.\n\n"
            "Create one with /createtemplate"
        )
        return ConversationHandler.END
    
    keyboard = []
    for tpl in templates:
        keyboard.append([InlineKeyboardButton(
            tpl['name'],
            callback_data=f"usetpl_{tpl['template_id']}"
        )])
    
    await update.message.reply_text(
        "📁 <b>Select Template</b>\n\n"
        "Choose which template to apply:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return WAITING_TEMPLATE_SELECT


async def receive_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle template selection"""
    query = update.callback_query
    await query.answer()
    
    template_id = query.data.replace("usetpl_", "")
    user_id = query.from_user.id
    
    template = await db.get_template(template_id)
    if not template:
        await query.edit_message_text("❌ Template not found!")
        return ConversationHandler.END
    
    user_data_store[user_id] = {"template": template}
    
    keyboard = [
        [InlineKeyboardButton("🌐 ALL Bots", callback_data="tpl_mode_all")],
        [InlineKeyboardButton("✅ Multiple Bots", callback_data="tpl_mode_multi")],
        [InlineKeyboardButton("🎯 Single Bot", callback_data="tpl_mode_single")],
    ]
    
    # Escape HTML in template name
    name = template['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    await query.edit_message_text(
        f"📁 <b>Template: {name}</b>\n\n"
        f"Where do you want to apply this template?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    return WAITING_TEMPLATE_MODE


async def receive_template_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle template application mode"""
    query = update.callback_query
    await query.answer()
    
    mode = query.data.replace("tpl_mode_", "")
    user_id = query.from_user.id
    
    if user_id not in user_data_store:
        await query.edit_message_text("❌ Session expired.")
        return ConversationHandler.END
    
    template = user_data_store[user_id]["template"]
    content = template["content"]
    
    if mode == "all":
        # Apply to all bots
        bots = await db.get_all_bots()
        bot_ids = [b["bot_id"] for b in bots]
        count = await db.update_bots_reply(bot_ids, content)
        
        # Update usage count
        await db.increment_template_usage(template["template_id"])
        
        await query.edit_message_text(
            f"✅ <b>Template Applied!</b>\n\n"
            f"Applied to {count} bots.",
            parse_mode="HTML"
        )
        
        del user_data_store[user_id]
        return ConversationHandler.END
    
    elif mode == "multi":
        # Show bot selection
        bots = await db.get_all_bots()
        keyboard = []
        for bot in bots[:10]:
            keyboard.append([InlineKeyboardButton(
                f"☐ @{bot['bot_username']}", 
                callback_data=f"tpltoggle_{bot['bot_id']}"
            )])
        keyboard.append([InlineKeyboardButton("✅ Apply", callback_data="tpl_apply")])
        
        user_data_store[user_id]["selected_bots"] = []
        user_data_store[user_id]["mode"] = "multi"
        
        await query.edit_message_text(
            "✅ <b>Select Bots</b>\n\n"
            "Tap to select/deselect:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
        return WAITING_TEMPLATE_MODE
    
    else:  # single
        bots = await db.get_all_bots()
        keyboard = [[InlineKeyboardButton(
            f"@{bot['bot_username']}", 
            callback_data=f"tplsingle_{bot['bot_id']}"
        )] for bot in bots[:15]]
        
        user_data_store[user_id]["mode"] = "single"
        
        await query.edit_message_text(
            "🎯 <b>Select Bot</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
        return WAITING_TEMPLATE_MODE


async def handle_template_bot_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot selection/application for templates"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_data_store:
        await query.answer("❌ Session expired!", show_alert=True)
        return ConversationHandler.END
    
    template = user_data_store[user_id]["template"]
    content = template["content"]
    
    # Handle toggle
    if query.data.startswith("tpltoggle_"):
        bot_id = query.data.replace("tpltoggle_", "")
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
                callback_data=f"tpltoggle_{bot['bot_id']}"
            )])
        keyboard.append([InlineKeyboardButton(f"✅ Apply ({len(selected)})", callback_data="tpl_apply")])
        
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        return WAITING_TEMPLATE_MODE
    
    # Handle apply
    elif query.data == "tpl_apply":
        await query.answer()
        selected = user_data_store[user_id].get("selected_bots", [])
        
        if not selected:
            await query.answer("❌ Select at least one bot!", show_alert=True)
            return WAITING_TEMPLATE_MODE
        
        count = await db.update_bots_reply(selected, content)
        await db.increment_template_usage(template["template_id"])
        
        await query.edit_message_text(
            f"✅ <b>Template Applied!</b>\n\n"
            f"Applied to {count} bots.",
            parse_mode="HTML"
        )
        
        del user_data_store[user_id]
        return ConversationHandler.END
    
    # Handle single bot
    elif query.data.startswith("tplsingle_"):
        await query.answer()
        bot_id = query.data.replace("tplsingle_", "")
        
        result = await db.db.bots.update_one(
            {"bot_id": bot_id},
            {"$set": {"auto_reply": content, "use_global_reply": False, "use_worker_reply": False}}
        )
        
        await db.increment_template_usage(template["template_id"])
        
        if result.modified_count > 0:
            await query.edit_message_text(
                "✅ <b>Template Applied!</b>",
                parse_mode="HTML"
            )
        
        del user_data_store[user_id]
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END