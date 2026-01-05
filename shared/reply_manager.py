"""
Reply Manager - Handles reply resolution with priority:
Bot-level > Worker-level > Global-level
"""

import re
from typing import Optional, Dict, Any
from datetime import datetime


class ReplyManager:
    """Manage reply resolution with variables"""
    
    @staticmethod
    def replace_variables(text: str, user_data: Dict[str, Any], bot_data: Dict[str, Any]) -> str:
        """Replace variables in text"""
        if not text:
            return text
        
        replacements = {
            '{user_name}': user_data.get('first_name', 'User'),
            '{user_id}': str(user_data.get('user_id', '')),
            '{username}': user_data.get('username', 'User'),
            '{bot_name}': bot_data.get('bot_username', '').replace('@', ''),
            '{bot_username}': bot_data.get('bot_username', ''),
        }
        
        result = text
        for var, value in replacements.items():
            result = result.replace(var, value)
        
        return result
    
    @staticmethod
    async def get_reply_for_bot(db, bot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the appropriate reply for a bot based on priority:
        1. Bot-specific reply (highest priority)
        2. Worker-level reply
        3. Global reply (lowest priority)
        """
        
        # Get bot data
        bot_data = await db.get_bot(bot_id)
        if not bot_data:
            return None
        
        # Priority 1: Bot-specific reply
        if bot_data.get('auto_reply') and not bot_data.get('use_global_reply', True):
            return bot_data['auto_reply']
        
        # Priority 2: Worker-level reply
        if bot_data.get('use_worker_reply', True):
            worker_reply = await db.get_worker_reply(bot_data['assigned_worker'])
            if worker_reply and worker_reply.get('enabled', True):
                return worker_reply.get('content')
        
        # Priority 3: Global reply
        if bot_data.get('use_global_reply', True):
            global_reply = await db.get_global_reply()
            if global_reply and global_reply.get('enabled', True):
                return global_reply.get('content')
        
        # Fallback: Bot-specific if exists
        return bot_data.get('auto_reply')
    
    @staticmethod
    def prepare_reply_text(reply_content: Dict[str, Any], user_data: Dict[str, Any], bot_data: Dict[str, Any]) -> str:
        """Prepare reply text with variable replacement"""
        text = reply_content.get('text', 'Hello! 👋')
        
        if reply_content.get('use_variables', True):
            text = ReplyManager.replace_variables(text, user_data, bot_data)
        
        return text
    
    @staticmethod
    def parse_message_to_reply(message) -> Dict[str, Any]:
        """Parse Telegram message to AutoReply format"""
        reply = {
            "text": None,
            "buttons": [],
            "media_type": None,
            "media_file_id": None,
            "use_variables": True
        }
        
        # Determine media type
        if message.photo:
            reply["media_type"] = "photo"
            reply["media_file_id"] = message.photo[-1].file_id
            reply["text"] = message.caption or ""
        elif message.video:
            reply["media_type"] = "video"
            reply["media_file_id"] = message.video.file_id
            reply["text"] = message.caption or ""
        elif message.document:
            reply["media_type"] = "document"
            reply["media_file_id"] = message.document.file_id
            reply["text"] = message.caption or ""
        elif message.text:
            text = message.text
            
            # Parse inline buttons from text
            pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
            matches = re.findall(pattern, text)
            
            if matches:
                # Remove button syntax from text
                clean_text = re.sub(pattern, '', text).strip()
                reply["text"] = clean_text
                
                # Create buttons
                for btn_text, btn_url in matches:
                    reply["buttons"].append([{"text": btn_text.strip(), "url": btn_url.strip()}])
            else:
                reply["text"] = text
        
        # Parse existing inline keyboard
        if message.reply_markup and message.reply_markup.inline_keyboard:
            for row in message.reply_markup.inline_keyboard:
                button_row = []
                for button in row:
                    if button.url:
                        button_row.append({"text": button.text, "url": button.url})
                if button_row:
                    reply["buttons"].append(button_row)
        
        return reply


# Global instance
reply_manager = ReplyManager()