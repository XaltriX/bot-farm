import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Database:
    """MongoDB connection handler"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
    
    async def connect(self):
        """Connect to MongoDB"""
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "bot_farm")
        
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        
        # Create indexes
        await self.create_indexes()
        logger.info(f"Connected to MongoDB: {db_name}")
    
    async def create_indexes(self):
        """Create required indexes"""
        # Bots collection
        await self.db.bots.create_index("bot_id", unique=True)
        await self.db.bots.create_index("assigned_worker")
        await self.db.bots.create_index("status")
        
        # Users collection
        await self.db.users.create_index([("bot_id", 1), ("user_id", 1)], unique=True)
        await self.db.users.create_index([("last_seen", -1)])
        await self.db.users.create_index("bot_id")
        
        # Broadcasts collection
        await self.db.broadcasts.create_index("broadcast_id", unique=True)
        await self.db.broadcasts.create_index("status")
        await self.db.broadcasts.create_index([("created_at", -1)])
        
        # Templates collection
        await self.db.templates.create_index("template_id", unique=True)
        await self.db.templates.create_index("name")
        
        # Global replies collection
        await self.db.global_replies.create_index("reply_id", unique=True)
        
        # Worker replies collection
        await self.db.worker_replies.create_index("worker_name", unique=True)
        
        logger.info("Database indexes created")
    
    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # Bot operations
    async def insert_bot(self, bot_data: Dict[str, Any]) -> bool:
        """Insert a new bot"""
        try:
            await self.db.bots.insert_one(bot_data)
            return True
        except Exception as e:
            logger.error(f"Error inserting bot: {e}")
            return False
    
    async def get_bot(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get bot by ID"""
        return await self.db.bots.find_one({"bot_id": bot_id})
    
    async def get_bots_by_worker(self, worker_name: str) -> List[Dict[str, Any]]:
        """Get all bots assigned to a worker"""
        cursor = self.db.bots.find({"assigned_worker": worker_name})
        return await cursor.to_list(length=None)
    
    async def update_bot_status(self, bot_id: str, status: str) -> bool:
        """Update bot status"""
        result = await self.db.bots.update_one(
            {"bot_id": bot_id},
            {"$set": {"status": status, "last_health_check": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def get_all_bots(self) -> List[Dict[str, Any]]:
        """Get all bots"""
        cursor = self.db.bots.find()
        return await cursor.to_list(length=None)
    
    async def delete_bot(self, bot_id: str) -> bool:
        """Delete a bot"""
        result = await self.db.bots.delete_one({"bot_id": bot_id})
        return result.deleted_count > 0
    
    # User operations
    async def upsert_user(self, user_id: int, bot_id: str) -> bool:
        """Insert or update user"""
        try:
            await self.db.users.update_one(
                {"user_id": user_id, "bot_id": bot_id},
                {
                    "$set": {"last_seen": datetime.utcnow()},
                    "$setOnInsert": {"first_seen": datetime.utcnow()}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error upserting user: {e}")
            return False
    
    async def get_users_by_bot(self, bot_id: str, skip: int = 0, limit: int = 1000):
        """Get users for a bot (paginated)"""
        cursor = self.db.users.find(
            {"bot_id": bot_id}
        ).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def count_users_by_bot(self, bot_id: str) -> int:
        """Count total users for a bot"""
        return await self.db.users.count_documents({"bot_id": bot_id})
    
    async def get_all_users_for_bots(self, bot_ids: List[str]):
        """Get all users across multiple bots"""
        cursor = self.db.users.find({"bot_id": {"$in": bot_ids}})
        async for user in cursor:
            yield user
    
    # Broadcast operations
    async def insert_broadcast(self, broadcast_data: Dict[str, Any]) -> bool:
        """Insert a new broadcast"""
        try:
            await self.db.broadcasts.insert_one(broadcast_data)
            return True
        except Exception as e:
            logger.error(f"Error inserting broadcast: {e}")
            return False
    
    async def get_broadcast(self, broadcast_id: str) -> Optional[Dict[str, Any]]:
        """Get broadcast by ID"""
        return await self.db.broadcasts.find_one({"broadcast_id": broadcast_id})
    
    async def update_broadcast_status(self, broadcast_id: str, status: str) -> bool:
        """Update broadcast status"""
        result = await self.db.broadcasts.update_one(
            {"broadcast_id": broadcast_id},
            {"$set": {"status": status}}
        )
        return result.modified_count > 0
    
    async def update_broadcast_stats(self, broadcast_id: str, sent: int, failed: int) -> bool:
        """Update broadcast statistics"""
        result = await self.db.broadcasts.update_one(
            {"broadcast_id": broadcast_id},
            {
                "$set": {
                    "sent_count": sent,
                    "failed_count": failed
                }
            }
        )
        return result.modified_count > 0
    
    # Template operations
    async def insert_template(self, template_data: Dict[str, Any]) -> bool:
        """Insert a new template"""
        try:
            await self.db.templates.insert_one(template_data)
            return True
        except Exception as e:
            logger.error(f"Error inserting template: {e}")
            return False
    
    async def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get template by ID"""
        return await self.db.templates.find_one({"template_id": template_id})
    
    async def get_all_templates(self) -> List[Dict[str, Any]]:
        """Get all templates"""
        cursor = self.db.templates.find().sort("created_at", -1)
        return await cursor.to_list(length=None)
    
    async def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        result = await self.db.templates.delete_one({"template_id": template_id})
        return result.deleted_count > 0
    
    async def increment_template_usage(self, template_id: str):
        """Increment template usage count"""
        await self.db.templates.update_one(
            {"template_id": template_id},
            {"$inc": {"usage_count": 1}}
        )
    
    # Global reply operations
    async def set_global_reply(self, reply_data: Dict[str, Any]) -> bool:
        """Set or update global reply"""
        try:
            await self.db.global_replies.update_one(
                {"reply_id": "global_default"},
                {"$set": reply_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error setting global reply: {e}")
            return False
    
    async def get_global_reply(self) -> Optional[Dict[str, Any]]:
        """Get global reply"""
        return await self.db.global_replies.find_one({"reply_id": "global_default"})
    
    # Worker reply operations
    async def set_worker_reply(self, worker_name: str, reply_data: Dict[str, Any]) -> bool:
        """Set or update worker reply"""
        try:
            reply_data["worker_name"] = worker_name
            await self.db.worker_replies.update_one(
                {"worker_name": worker_name},
                {"$set": reply_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error setting worker reply: {e}")
            return False
    
    async def get_worker_reply(self, worker_name: str) -> Optional[Dict[str, Any]]:
        """Get worker reply"""
        return await self.db.worker_replies.find_one({"worker_name": worker_name})
    
    # Bulk bot operations
    async def update_bots_reply(self, bot_ids: List[str], auto_reply: Dict[str, Any]) -> int:
        """Update auto reply for multiple bots"""
        result = await self.db.bots.update_many(
            {"bot_id": {"$in": bot_ids}},
            {"$set": {"auto_reply": auto_reply, "use_global_reply": False, "use_worker_reply": False}}
        )
        return result.modified_count
    
    async def enable_global_reply_for_bots(self, bot_ids: List[str]) -> int:
        """Enable global reply for multiple bots"""
        result = await self.db.bots.update_many(
            {"bot_id": {"$in": bot_ids}},
            {"$set": {"use_global_reply": True, "auto_reply": None}}
        )
        return result.modified_count
    
    async def enable_worker_reply_for_bots(self, bot_ids: List[str]) -> int:
        """Enable worker reply for multiple bots"""
        result = await self.db.bots.update_many(
            {"bot_id": {"$in": bot_ids}},
            {"$set": {"use_worker_reply": True, "use_global_reply": False, "auto_reply": None}}
        )
        return result.modified_count


# Global database instance
db = Database()