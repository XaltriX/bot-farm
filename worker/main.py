import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv
from telegram import Bot

from shared import db, redis_client, Crypto
from .webhook_handler import webhook_handler
from .broadcast_engine import get_broadcast_engine
from .health_checker import get_health_checker

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Worker configuration
WORKER_NAME = os.getenv("WORKER_NAME", "worker-1")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")

# Background tasks
background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info(f"Starting worker: {WORKER_NAME}")
    
    # Connect to databases
    await db.connect()
    await redis_client.connect()
    
    # Setup webhooks for all bots
    await setup_webhooks()
    
    # Start background tasks
    broadcast_engine = get_broadcast_engine(WORKER_NAME)
    health_checker = get_health_checker(WORKER_NAME)
    
    task1 = asyncio.create_task(broadcast_engine.monitor_broadcasts())
    task2 = asyncio.create_task(health_checker.start_monitoring())
    
    background_tasks.add(task1)
    background_tasks.add(task2)
    
    logger.info(f"Worker {WORKER_NAME} started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down worker...")
    
    # Cancel background tasks
    for task in background_tasks:
        task.cancel()
    
    await db.disconnect()
    await redis_client.disconnect()
    
    logger.info("Worker shutdown complete")


app = FastAPI(lifespan=lifespan)


async def setup_webhooks():
    """Setup webhooks for all bots assigned to this worker"""
    logger.info("Setting up webhooks...")
    
    bots = await db.get_bots_by_worker(WORKER_NAME)
    crypto = Crypto()
    
    # Get Heroku domain or use environment variable
    webhook_domain = os.getenv("WEBHOOK_DOMAIN", "").rstrip('/')
    if not webhook_domain:
        logger.warning("⚠️ WEBHOOK_DOMAIN not set, skipping webhook setup")
        return
    
    for bot_data in bots:
        try:
            token = crypto.decrypt(bot_data["token"])
            bot = Bot(token)
            
            webhook_url = f"{webhook_domain}/webhook/{WORKER_NAME}/{bot_data['bot_id']}"
            
            await bot.set_webhook(
                url=webhook_url,
                secret_token=bot_data["secret_token"],
                allowed_updates=["message"]
            )
            
            logger.info(f"✅ Webhook set for {bot_data['bot_id']}")
            
        except Exception as e:
            logger.error(f"✗ Webhook failed for {bot_data['bot_id']} → {e}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "worker": WORKER_NAME
    }


@app.post("/webhook/{worker_name}/{bot_id}")
async def webhook_endpoint(
    worker_name: str,
    bot_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Handle webhook requests from Telegram"""
    
    # Verify worker name
    if worker_name != WORKER_NAME:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # Verify secret token
    if not await webhook_handler.verify_secret(bot_id, x_telegram_bot_api_secret_token):
        logger.warning(f"Invalid secret token for bot {bot_id}")
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Get update data
    update_data = await request.json()
    
    # Handle in background
    asyncio.create_task(webhook_handler.handle_message(bot_id, update_data))
    
    return {"ok": True}


@app.get("/stats")
async def stats():
    """Get worker statistics"""
    bots = await db.get_bots_by_worker(WORKER_NAME)
    
    total_users = 0
    for bot in bots:
        count = await db.count_users_by_bot(bot["bot_id"])
        total_users += count
    
    return {
        "worker": WORKER_NAME,
        "total_bots": len(bots),
        "total_users": total_users,
        "alive_bots": sum(1 for b in bots if b["status"] == "alive")
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
