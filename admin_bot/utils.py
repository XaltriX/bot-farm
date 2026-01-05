import os
import secrets
import uuid
from typing import List
from telegram import InlineKeyboardButton


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    admin_ids = [int(uid.strip()) for uid in admin_ids_str.split(",") if uid.strip()]
    return user_id in admin_ids


def generate_bot_id() -> str:
    """Generate unique bot ID"""
    return str(uuid.uuid4())


def generate_secret_token() -> str:
    """Generate webhook secret token"""
    return secrets.token_urlsafe(32)


def generate_broadcast_id() -> str:
    """Generate unique broadcast ID"""
    return f"bc_{uuid.uuid4().hex[:12]}"


def parse_inline_buttons(entities) -> List[List[InlineKeyboardButton]]:
    """Parse inline buttons from message entities"""
    buttons = []
    
    if not entities:
        return buttons
    
    for entity in entities:
        if entity.type == "text_link":
            # This is a URL button
            button = InlineKeyboardButton(text=entity.url, url=entity.url)
            buttons.append([button])
    
    return buttons


def format_bot_stats(bot_data: dict, user_count: int) -> str:
    """Format bot statistics"""
    return (
        f"🤖 Bot: @{bot_data['bot_username']}\n"
        f"📊 Status: {bot_data['status']}\n"
        f"👥 Users: {user_count:,}\n"
        f"⚙️ Worker: {bot_data['assigned_worker']}\n"
        f"📅 Created: {bot_data['created_at'].strftime('%Y-%m-%d %H:%M')}"
    )


def format_broadcast_stats(stats: dict, total_users: int) -> str:
    """Format broadcast statistics"""
    progress = (stats['sent'] + stats['failed']) / total_users * 100 if total_users > 0 else 0
    
    return (
        f"📊 Broadcast Statistics\n\n"
        f"Status: {stats['status']}\n"
        f"Progress: {progress:.1f}%\n\n"
        f"✅ Sent: {stats['sent']:,}\n"
        f"❌ Failed: {stats['failed']:,}\n"
        f"📝 Total Users: {total_users:,}\n"
        f"📍 Current Index: {stats['current_index']:,}"
    )


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Split list into chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]