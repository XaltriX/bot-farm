"""Bulk Bot Upload Handler"""

import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from shared import db, Crypto, BotModel
from .handlers import is_admin, user_data_store
from .utils import generate_bot_id, generate_secret_token

logger = logging.getLogger(__name__)

WAITING_BULK_FILE, WAITING_BULK_WORKER = range(100, 102)


async def bulk_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start bulk upload process"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📁 *Bulk Bot Upload*\n\n"
        "Upload a `.txt` file with bot tokens.\n\n"
        "**Format (one token per line):**\n"
        "```\n"
        "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11\n"
        "789012:XYZ-GHI5678jkLmn-abc12P3q4r567st22\n"
        "345678:QRS-TUV9012opQrs-def34T5u6v789wx33\n"
        "```\n\n"
        "Or with worker names (format: `token,worker`):\n"
        "```\n"
        "123456:ABC...,worker-1\n"
        "789012:XYZ...,worker-2\n"
        "345678:QRS...,worker-1\n"
        "```\n\n"
        "Send the file now:",
        parse_mode="Markdown"
    )
    
    return WAITING_BULK_FILE


async def receive_bulk_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process bulk file"""
    user_id = update.effective_user.id
    
    if not update.message.document:
        await update.message.reply_text(
            "❌ Please send a `.txt` file!\n\n"
            "Or /cancel to exit."
        )
        return WAITING_BULK_FILE
    
    document = update.message.document
    
    # Check file type
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text(
            "❌ File must be a `.txt` file!\n\n"
            "Or /cancel to exit."
        )
        return WAITING_BULK_FILE
    
    # Download file
    try:
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        content = file_content.decode('utf-8')
        
        # Parse tokens
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not lines:
            await update.message.reply_text("❌ File is empty!")
            return ConversationHandler.END
        
        # Parse tokens and workers
        tokens_data = []
        has_workers = False
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.startswith('#'):
                continue
            
            # Check if format is token,worker
            if ',' in line:
                parts = line.split(',')
                if len(parts) == 2:
                    token = parts[0].strip()
                    worker = parts[1].strip()
                    tokens_data.append({'token': token, 'worker': worker})
                    has_workers = True
                else:
                    tokens_data.append({'token': line, 'worker': None})
            else:
                tokens_data.append({'token': line, 'worker': None})
        
        if not tokens_data:
            await update.message.reply_text("❌ No valid tokens found!")
            return ConversationHandler.END
        
        # Store data
        user_data_store[user_id] = {
            'tokens_data': tokens_data,
            'has_workers': has_workers
        }
        
        # If all tokens have workers, start processing
        if has_workers and all(t['worker'] for t in tokens_data):
            await update.message.reply_text(
                f"📊 *File Processed*\n\n"
                f"Found: {len(tokens_data)} tokens with workers\n\n"
                f"Starting validation...",
                parse_mode="Markdown"
            )
            
            # Process immediately
            await process_bulk_tokens(update, context, user_id)
            return ConversationHandler.END
        else:
            # Ask for default worker
            await update.message.reply_text(
                f"📊 *File Processed*\n\n"
                f"Found: {len(tokens_data)} tokens\n\n"
                f"Which worker should handle these bots?\n"
                f"(e.g., `worker-1`, `worker-2`)\n\n"
                f"You can also use round-robin by sending `auto`",
                parse_mode="Markdown"
            )
            return WAITING_BULK_WORKER
    
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text(
            f"❌ Error processing file: {str(e)}\n\n"
            "Make sure file is UTF-8 encoded."
        )
        return ConversationHandler.END


async def receive_bulk_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive worker assignment for bulk upload"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("❌ Session expired. Start over with /bulkupload")
        return ConversationHandler.END
    
    worker_input = update.message.text.strip().lower()
    
    data = user_data_store[user_id]
    tokens_data = data['tokens_data']
    
    # If auto, distribute across workers
    if worker_input == 'auto':
        # Get existing workers
        bots = await db.get_all_bots()
        workers = list(set(b['assigned_worker'] for b in bots)) if bots else ['worker-1']
        
        # Round-robin assignment
        for idx, token_data in enumerate(tokens_data):
            if not token_data['worker']:
                token_data['worker'] = workers[idx % len(workers)]
        
        await update.message.reply_text(
            f"🔄 *Auto Distribution*\n\n"
            f"Distributing across {len(workers)} workers...\n\n"
            f"Starting validation...",
            parse_mode="Markdown"
        )
    else:
        # Assign all to specified worker
        for token_data in tokens_data:
            if not token_data['worker']:
                token_data['worker'] = worker_input
        
        await update.message.reply_text(
            f"⚙️ *Worker: {worker_input}*\n\n"
            f"Starting validation...",
            parse_mode="Markdown"
        )
    
    # Process tokens
    await process_bulk_tokens(update, context, user_id)
    
    return ConversationHandler.END


async def process_bulk_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Process and validate bulk tokens"""
    
    if user_id not in user_data_store:
        return
    
    data = user_data_store[user_id]
    tokens_data = data['tokens_data']
    
    from telegram import Bot
    
    crypto = Crypto()
    
    results = {
        'success': [],
        'failed': [],
        'duplicate': []
    }
    
    total = len(tokens_data)
    
    # Progress message
    progress_msg = await update.message.reply_text(
        f"⏳ Processing 0/{total} tokens..."
    )
    
    for idx, token_data in enumerate(tokens_data, 1):
        token = token_data['token']
        worker = token_data['worker']
        
        try:
            # Validate token
            test_bot = Bot(token)
            bot_info = await test_bot.get_me()
            bot_username = bot_info.username
            
            # Check if already exists
            existing = await db.db.bots.find_one({"bot_username": bot_username})
            if existing:
                results['duplicate'].append({
                    'username': bot_username,
                    'reason': 'Already exists'
                })
                continue
            
            # Encrypt token
            encrypted_token = crypto.encrypt(token)
            
            # Create bot entry
            bot_id = generate_bot_id()
            secret_token = generate_secret_token()
            
            bot_data = BotModel(
                bot_id=bot_id,
                bot_username=bot_username,
                token=encrypted_token,
                secret_token=secret_token,
                assigned_worker=worker,
                use_global_reply=True
            ).model_dump()
            
            # Save to database
            success = await db.insert_bot(bot_data)
            
            if success:
                results['success'].append({
                    'username': bot_username,
                    'worker': worker,
                    'bot_id': bot_id
                })
            else:
                results['failed'].append({
                    'token': token[:20] + '...',
                    'reason': 'Database insert failed'
                })
            
            # Update progress every 5 bots or at end
            if idx % 5 == 0 or idx == total:
                await progress_msg.edit_text(
                    f"⏳ Processing {idx}/{total} tokens...\n"
                    f"✅ Success: {len(results['success'])}\n"
                    f"❌ Failed: {len(results['failed'])}\n"
                    f"⚠️ Duplicate: {len(results['duplicate'])}"
                )
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)
            
        except Exception as e:
            results['failed'].append({
                'token': token[:20] + '...',
                'reason': str(e)
            })
    
    # Final summary
    summary = (
        f"✅ *Bulk Upload Complete!*\n\n"
        f"📊 **Summary:**\n"
        f"├ Total Processed: {total}\n"
        f"├ ✅ Success: {len(results['success'])}\n"
        f"├ ❌ Failed: {len(results['failed'])}\n"
        f"└ ⚠️ Duplicate: {len(results['duplicate'])}\n\n"
    )
    
    # Success details
    if results['success']:
        summary += f"**✅ Successfully Added ({len(results['success'])}):**\n"
        for bot in results['success'][:10]:  # Show first 10
            summary += f"├ @{bot['username']} → {bot['worker']}\n"
        if len(results['success']) > 10:
            summary += f"└ ... and {len(results['success']) - 10} more\n"
        summary += "\n"
    
    # Failed details
    if results['failed']:
        summary += f"**❌ Failed ({len(results['failed'])}):**\n"
        for fail in results['failed'][:5]:  # Show first 5
            summary += f"├ {fail['token']}\n"
            summary += f"│  Reason: {fail['reason']}\n"
        if len(results['failed']) > 5:
            summary += f"└ ... and {len(results['failed']) - 5} more\n"
        summary += "\n"
    
    # Duplicate details
    if results['duplicate']:
        summary += f"**⚠️ Duplicate ({len(results['duplicate'])}):**\n"
        for dup in results['duplicate'][:5]:  # Show first 5
            summary += f"├ @{dup['username']}\n"
        if len(results['duplicate']) > 5:
            summary += f"└ ... and {len(results['duplicate']) - 5} more\n"
    
    await progress_msg.edit_text(summary, parse_mode="Markdown")
    
    # Cleanup
    del user_data_store[user_id]


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel bulk upload"""
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    
    await update.message.reply_text("❌ Bulk upload cancelled.")
    return ConversationHandler.END