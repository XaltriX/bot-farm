import os
import logging
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import telegram

from shared import db, redis_client
from .handlers import (
    start,
    add_bot_start,
    receive_token,
    receive_worker,
    list_bots,
    stats,
    receive_reply_mode,
    set_reply_start,
    receive_worker_selection,
    toggle_bot_selection,
    receive_single_bot_selection,
    receive_reply_message,
    view_reply,
    global_reply_shortcut,
    cancel,
    WAITING_TOKEN,
    WAITING_WORKER,
    WAITING_REPLY_MODE,
    WAITING_WORKER_SELECT,
    WAITING_MULTI_SELECT,
    WAITING_BOT_SELECT,
    WAITING_REPLY_MESSAGE,
)
from .handlers_templates import (
    create_template_start,
    receive_template_name,
    receive_template_desc,
    receive_template_content,
    list_templates,
    use_template_start,
    receive_template_selection,
    receive_template_mode,
    handle_template_bot_action,
    WAITING_TEMPLATE_NAME,
    WAITING_TEMPLATE_DESC,
    WAITING_TEMPLATE_CONTENT,
    WAITING_TEMPLATE_SELECT,
    WAITING_TEMPLATE_MODE
)
from .bulk_upload import (
    bulk_upload_start,
    receive_bulk_file,
    receive_bulk_worker,
    WAITING_BULK_FILE,
    WAITING_BULK_WORKER
)
from .quick_replies import (
    global_reply_start,
    receive_global_message,
    worker_reply_start,
    receive_worker_name,
    receive_worker_message,
    WAITING_GLOBAL_MESSAGE,
    WAITING_WORKER_NAME,
    WAITING_WORKER_MESSAGE
)
from .broadcast_health import broadcast_start, receive_broadcast_message, health_check, WAITING_BROADCAST_MESSAGE

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors - prevent crashes on network issues"""
    logger.error(f"Exception: {context.error}")
    
    # Ignore network errors
    if isinstance(context.error, telegram.error.NetworkError):
        logger.warning("Network error - continuing...")
        return


async def post_init(application: Application):
    """Initialize connections after bot starts"""
    await db.connect()
    await redis_client.connect()
    logger.info("Admin bot initialized")


async def post_shutdown(application: Application):
    """Cleanup connections on shutdown"""
    await db.disconnect()
    await redis_client.disconnect()
    logger.info("Admin bot shutdown")


def main():
    """Start the admin bot"""
    token = os.getenv("ADMIN_BOT_TOKEN")
    
    if not token:
        raise ValueError("ADMIN_BOT_TOKEN not set")
    
    # Increase timeouts for network stability
    from telegram.request import HTTPXRequest
    
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    
    application = (
        Application.builder()
        .token(token)
        .request(request)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Add bot conversation handler
    add_bot_conv = ConversationHandler(
        entry_points=[CommandHandler("addbot", add_bot_start)],
        states={
            WAITING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            WAITING_WORKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_worker)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Set reply conversation handler
    set_reply_conv = ConversationHandler(
        entry_points=[CommandHandler("setreply", set_reply_start)],
        states={
            WAITING_REPLY_MODE: [CallbackQueryHandler(receive_reply_mode, pattern="^reply_mode_")],
            WAITING_WORKER_SELECT: [CallbackQueryHandler(receive_worker_selection, pattern="^worker_")],
            WAITING_MULTI_SELECT: [
                CallbackQueryHandler(toggle_bot_selection, pattern="^togglebot_"),
                CallbackQueryHandler(toggle_bot_selection, pattern="^multi_done$")
            ],
            WAITING_BOT_SELECT: [CallbackQueryHandler(receive_single_bot_selection, pattern="^singlebot_")],
            WAITING_REPLY_MESSAGE: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND,
                    receive_reply_message
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Create template conversation handler
    create_template_conv = ConversationHandler(
        entry_points=[CommandHandler("createtemplate", create_template_start)],
        states={
            WAITING_TEMPLATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_template_name)],
            WAITING_TEMPLATE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_template_desc)],
            WAITING_TEMPLATE_CONTENT: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
                    receive_template_content
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Use template conversation handler
    use_template_conv = ConversationHandler(
        entry_points=[CommandHandler("usetemplate", use_template_start)],
        states={
            WAITING_TEMPLATE_SELECT: [CallbackQueryHandler(receive_template_selection, pattern="^usetpl_")],
            WAITING_TEMPLATE_MODE: [
                CallbackQueryHandler(receive_template_mode, pattern="^tpl_mode_"),
                CallbackQueryHandler(handle_template_bot_action, pattern="^tpltoggle_"),
                CallbackQueryHandler(handle_template_bot_action, pattern="^tpl_apply$"),
                CallbackQueryHandler(handle_template_bot_action, pattern="^tplsingle_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Broadcast conversation handler
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO | 
                     filters.AUDIO | filters.Document.ALL) & ~filters.COMMAND,
                    receive_broadcast_message
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Bulk upload conversation handler
    bulk_upload_conv = ConversationHandler(
        entry_points=[CommandHandler("bulkupload", bulk_upload_start)],
        states={
            WAITING_BULK_FILE: [
                MessageHandler(filters.Document.ALL & ~filters.COMMAND, receive_bulk_file)
            ],
            WAITING_BULK_WORKER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bulk_worker)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Global reply conversation handler
    global_reply_conv = ConversationHandler(
        entry_points=[CommandHandler("globalreply", global_reply_start)],
        states={
            WAITING_GLOBAL_MESSAGE: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
                    receive_global_message
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Worker reply conversation handler
    worker_reply_conv = ConversationHandler(
        entry_points=[CommandHandler("workerreply", worker_reply_start)],
        states={
            WAITING_WORKER_NAME: [CallbackQueryHandler(receive_worker_name, pattern="^wreply_")],
            WAITING_WORKER_MESSAGE: [
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND,
                    receive_worker_message
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    
    # Add all handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(add_bot_conv)
    application.add_handler(set_reply_conv)
    application.add_handler(create_template_conv)
    application.add_handler(use_template_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(bulk_upload_conv)
    application.add_handler(global_reply_conv)
    application.add_handler(worker_reply_conv)
    application.add_handler(CommandHandler("listbots", list_bots))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CommandHandler("viewreply", view_reply))
    application.add_handler(CommandHandler("templates", list_templates))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting admin bot...")
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        poll_interval=3.0,
        timeout=30,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()