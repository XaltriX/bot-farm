# shared/__init__.py

# Import classes first (no instantiation)
from .database import Database
from .redis_client import RedisClient
from .crypto import Crypto, generate_encryption_key
from .reply_manager import ReplyManager

from .models import (
    BotModel,
    UserModel,
    BroadcastModel,
    BotStatus,
    BroadcastStatus,
    AutoReply,
    InlineButton,
    BroadcastContent,
    BroadcastStats,
    ReplyTemplate,
    GlobalReply,
    WorkerReply,
    ReplyMode
)

# Create singleton instances for database and redis ONLY
# These don't need env vars in __init__
db = Database()
redis_client = RedisClient()

# DON'T create reply_manager here if it needs Crypto!
# Let each module create it when needed after .env is loaded
reply_manager = None  # Will be initialized later

def init_reply_manager():
    """Initialize reply_manager after .env is loaded"""
    global reply_manager
    if reply_manager is None:
        reply_manager = ReplyManager()
    return reply_manager


__all__ = [
    "db",
    "Database",
    "redis_client",
    "RedisClient",
    "Crypto",
    "generate_encryption_key",
    "reply_manager",
    "ReplyManager",
    "init_reply_manager",  # Export the init function
    "BotModel",
    "UserModel",
    "BroadcastModel",
    "BotStatus",
    "BroadcastStatus",
    "AutoReply",
    "InlineButton",
    "BroadcastContent",
    "BroadcastStats",
    "ReplyTemplate",
    "GlobalReply",
    "WorkerReply",
    "ReplyMode"
]