import os
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header
from dotenv import load_dotenv
from telegram import Bot

# ===== CRITICAL: FORCE LOAD .env FIRST =====
BASE_DIR = Path(__file__).resolve().parent.parent
env_file = BASE_DIR / ".env"
load_dotenv(env_file)

# Debug print to verify
print(f"[WORKER] Loading .env from: {env_file}")
print(f"[WORKER] .env exists: {env_file.exists()}")
print(f"[WORKER] ENCRYPTION_KEY: {'✓ LOADED' if os.getenv('ENCRYPTION_KEY') else '✗ MISSING'}")

# ===== NOW SAFE TO IMPORT SHARED MODULES =====
from shared import db, redis_client
from shared.crypto import Crypto  # Import class, NOT instance
from .webhook_handler import get_webhook_handler
from .broadcast_engine import get_broadcast_engine
from .health_checker import get_health_checker

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WORKER_NAME = os.getenv("WORKER_NAME", "worker-1")
WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")

background_tasks = set()
webhook_handler = get_webhook_handler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting worker: {WORKER_NAME}")
    
    # Connect to databases
    await db.connect()
    await redis_client.connect()
    
    # Setup webhooks
    await setup_webhooks()
    
    # Start background tasks
    broadcast_engine = get_broadcast_engine(WORKER_NAME)
    health_checker = get_health_checker(WORKER_NAME)
    
    background_tasks.add(asyncio.create_task(
        broadcast_engine.monitor_broadcasts()
    ))
    background_tasks.add(asyncio.create_task(
        health_checker.start_monitoring()
    ))
    
    yield
    
    # Cleanup
    logger.info("Shutting down worker...")
    for task in background_tasks:
        task.cancel()
    await db.disconnect()
    await redis_client.disconnect()


app = FastAPI(lifespan=lifespan)


async def setup_webhooks():
    """Setup webhooks for all bots assigned to this worker"""
    logger.info("Setting up webhooks...")
    bots = await db.get_bots_by_worker(WORKER_NAME)
    crypto = Crypto()  # Create instance here, AFTER .env is loaded
    
    for bot_data in bots:
        try:
            token = crypto.decrypt(bot_data["token"])
            bot = Bot(token)
            webhook_url = (
                f"{WEBHOOK_DOMAIN}/webhook/{WORKER_NAME}/{bot_data['bot_id']}"
            )
            await bot.set_webhook(
                url=webhook_url,
                secret_token=bot_data["secret_token"],
                allowed_updates=["message"]
            )
            logger.info(f"✓ Webhook set for bot {bot_data['bot_id']}")
        except Exception as e:
            logger.error(
                f"✗ Webhook failed for {bot_data['bot_id']} → {e}"
            )


@app.get("/")
async def root():
    return {"status": "ok", "worker": WORKER_NAME}


@app.post("/webhook/{worker_name}/{bot_id}")
async def webhook_endpoint(
    worker_name: str,
    bot_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    if worker_name != WORKER_NAME:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    if not await webhook_handler.verify_secret(
        bot_id, x_telegram_bot_api_secret_token
    ):
        raise HTTPException(status_code=403, detail="Invalid secret token")
    
    data = await request.json()
    
    # Process webhook asynchronously
    asyncio.create_task(
        webhook_handler.handle_message(bot_id, data)
    )
    
    return {"ok": True}


@app.get("/stats")
async def stats():
    """Get worker statistics"""
    bots = await db.get_bots_by_worker(WORKER_NAME)
    total_users = 0
    
    for bot in bots:
        total_users += await db.count_users_by_bot(bot["bot_id"])
    
    return {
        "worker": WORKER_NAME,
        "total_bots": len(bots),
        "total_users": total_users,
        "alive_bots": sum(1 for b in bots if b["status"] == "alive"),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "worker": WORKER_NAME,
        "db_connected": db.client is not None,
        "redis_connected": redis_client.redis is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("WEBHOOK_PORT", 8000))
    )