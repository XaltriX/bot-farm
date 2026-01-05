from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class BotStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"
    PAUSED = "paused"


class BroadcastStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ReplyMode(str, Enum):
    GLOBAL = "global"  # Applies to all bots
    WORKER = "worker"  # Applies to specific worker
    BOT = "bot"        # Applies to specific bot


class InlineButton(BaseModel):
    text: str
    url: str


class AutoReply(BaseModel):
    text: str
    buttons: List[List[InlineButton]] = []
    media_type: Optional[str] = None  # photo, video, document
    media_file_id: Optional[str] = None
    use_variables: bool = True  # Enable variable replacement


class ReplyTemplate(BaseModel):
    template_id: str
    name: str
    description: Optional[str] = None
    content: AutoReply
    created_at: datetime = Field(default_factory=datetime.utcnow)
    usage_count: int = 0


class BotModel(BaseModel):
    bot_id: str
    bot_username: str
    token: str  # encrypted
    secret_token: str
    assigned_worker: str
    status: BotStatus = BotStatus.ALIVE
    auto_reply: Optional[AutoReply] = None
    use_global_reply: bool = True  # If true, uses global reply
    use_worker_reply: bool = True  # If true, uses worker reply
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None


class GlobalReply(BaseModel):
    reply_id: str = "global_default"
    content: AutoReply
    enabled: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkerReply(BaseModel):
    worker_name: str
    content: AutoReply
    enabled: bool = True
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserModel(BaseModel):
    user_id: int
    bot_id: str
    first_name: Optional[str] = None
    username: Optional[str] = None
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 1


class BroadcastContent(BaseModel):
    content_type: str  # text, photo, video, audio, document
    text: Optional[str] = None
    file_id: Optional[str] = None
    caption: Optional[str] = None
    buttons: List[List[InlineButton]] = []


class BroadcastModel(BaseModel):
    broadcast_id: str
    bot_ids: List[str]
    content: BroadcastContent
    status: BroadcastStatus = BroadcastStatus.RUNNING
    total_users: int = 0
    sent_count: int = 0
    failed_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BroadcastStats(BaseModel):
    broadcast_id: str
    status: BroadcastStatus
    current_index: int
    sent: int
    failed: int
    total: int
    progress_percent: float