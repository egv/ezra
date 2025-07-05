import os
import asyncio
import hashlib
import logging
from datetime import datetime, time
from typing import List

from telegram import Update, Chat
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from database import Database
from llm_service import LLMService

load_dotenv(override=False)  # Don't override existing environment variables

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_USERNAME = "jewpacabra"

class EzraBot:
    def __init__(self):
        self.db = Database()
        self.llm = LLMService()
        self.scheduler = AsyncIOScheduler()
        self.application = None

    async def initialize(self):
        await self.db.init_db()
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        self.application = Application.builder().token(token).build()
        
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("digest", self.digest_command))
        self.application.add_handler(CommandHandler("list_channels", self.list_channels_command))
        self.application.add_handler(CommandHandler("add_channel", self.add_channel_command))
        self.application.add_handler(CommandHandler("remove_channel", self.remove_channel_command))
        self.application.add_handler(CommandHandler("regenerate", self.regenerate_digest_command))
        self.application.add_handler(MessageHandler(filters.FORWARDED, self.handle_forwarded_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.db.add_user(user.id, user.username)
        await self.db.subscribe_user(user.id)
        
        await update.message.reply_text(
            "Welcome to Ezra! 🤖\n\n"
            "You've been subscribed to receive daily digests at 08:00.\n"
            "Use /digest to get the latest digest anytime.\n"
            "Use /stop to unsubscribe from daily digests."
        )

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await self.db.unsubscribe_user(user.id)
        
        await update.message.reply_text(
            "You've been unsubscribed from daily digests. "
            "Use /start to subscribe again."
        )

    async def digest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        digest = await self.db.get_latest_digest()
        
        if digest:
            await update.message.reply_text(digest, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "No digest available yet. The daily digest will be generated at 08:00."
            )

    async def list_channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.username != ADMIN_USERNAME:
            await update.message.reply_text("This command is only available to admins.")
            return
        
        channels = await self.db.get_channels()
        
        if not channels:
            await update.message.reply_text("No channels configured.")
            return
        
        message = "📋 *Configured Channels:*\n\n"
        for channel_id, channel_name, channel_username in channels:
            username_text = f"@{channel_username}" if channel_username else "No username"
            message += f"• {channel_name} ({username_text})\n  ID: `{channel_id}`\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')

    async def add_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.username != ADMIN_USERNAME:
            await update.message.reply_text("This command is only available to admins.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /add_channel <channel_id>\n"
                "You can also forward a message from the channel to add it automatically."
            )
            return
        
        try:
            channel_id = int(context.args[0])
            
            try:
                chat = await context.bot.get_chat(channel_id)
                await self.db.add_channel(channel_id, chat.title, chat.username, user.id)
                await update.message.reply_text(f"✅ Added channel: {chat.title}")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to add channel: {str(e)}")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid channel ID. Please provide a numeric channel ID.")

    async def remove_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.username != ADMIN_USERNAME:
            await update.message.reply_text("This command is only available to admins.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /remove_channel <channel_id>")
            return
        
        try:
            channel_id = int(context.args[0])
            success = await self.db.remove_channel(channel_id)
            
            if success:
                await update.message.reply_text(f"✅ Removed channel with ID: {channel_id}")
            else:
                await update.message.reply_text(f"❌ Failed to remove channel with ID: {channel_id}")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid channel ID. Please provide a numeric channel ID.")

    async def regenerate_digest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.username != ADMIN_USERNAME:
            await update.message.reply_text("This command is only available to admins.")
            return
        
        await update.message.reply_text("🔄 Regenerating today's digest...")
        
        try:
            await self.regenerate_digest_from_today()
            await update.message.reply_text("✅ Digest regenerated and sent to all subscribed users!")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to regenerate digest: {str(e)}")

    async def regenerate_digest_from_today(self):
        """Regenerate digest from all today's messages (not just unprocessed)"""
        try:
            logger.info("Starting digest regeneration from today's messages...")
            
            messages = await self.db.get_todays_messages()
            
            if not messages:
                logger.info("No messages found for today")
                return
            
            # Pass full message data for source link generation
            digest = await self.llm.generate_digest_with_sources(messages)
            
            today = datetime.now().strftime("%Y-%m-%d")
            await self.db.save_digest(today, digest)
            
            subscribed_users = await self.db.get_subscribed_users()
            
            for user_id in subscribed_users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=digest,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send digest to user {user_id}: {e}")
            
            logger.info(f"Digest regenerated and sent to {len(subscribed_users)} users")
            
        except Exception as e:
            logger.error(f"Error regenerating digest: {e}")

    async def handle_forwarded_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if user.username != ADMIN_USERNAME:
            return
        
        if update.message.forward_origin:
            origin = update.message.forward_origin
            
            if hasattr(origin, 'chat') and origin.chat.type == Chat.CHANNEL:
                channel = origin.chat
                
                # First, try to add the channel
                success = await self.db.add_channel(
                    channel.id, 
                    channel.title, 
                    channel.username, 
                    user.id
                )
                
                # Save the forwarded message content if it exists
                message_content = update.message.text or update.message.caption
                if message_content:
                    content_hash = hashlib.md5(message_content.encode()).hexdigest()
                    message_date = update.message.forward_origin.date if hasattr(update.message.forward_origin, 'date') else update.message.date
                    
                    message_saved = await self.db.add_message(
                        channel.id, message_content, message_date, content_hash
                    )
                    
                    if message_saved:
                        logger.info(f"Saved forwarded message from channel {channel.id}")
                
                if success:
                    message_status = "📝 Message saved!" if message_content else ""
                    await update.message.reply_text(
                        f"✅ Added channel: {channel.title}\n{message_status}\n\n"
                        "Forward more messages from this channel to build the digest!"
                    )
                else:
                    # Channel already exists, just save the message
                    if message_content:
                        await update.message.reply_text("📝 Message saved from known channel!")
                    else:
                        await update.message.reply_text("Channel already tracked!")

    async def generate_and_send_digest(self):
        try:
            logger.info("Starting digest generation...")
            
            messages = await self.db.get_unprocessed_messages()
            
            if not messages:
                logger.info("No new messages to process")
                return
            
            # Pass full message data for source link generation
            digest = await self.llm.generate_digest_with_sources(messages)
            
            today = datetime.now().strftime("%Y-%m-%d")
            await self.db.save_digest(today, digest)
            
            message_ids = [msg[0] for msg in messages]
            await self.db.mark_messages_processed(message_ids)
            
            subscribed_users = await self.db.get_subscribed_users()
            
            for user_id in subscribed_users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=digest,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send digest to user {user_id}: {e}")
            
            logger.info(f"Digest sent to {len(subscribed_users)} users")
            
        except Exception as e:
            logger.error(f"Error generating digest: {e}")

    def start_scheduler(self):
        self.scheduler.add_job(
            func=self.generate_and_send_digest,
            trigger=CronTrigger(hour=8, minute=0),
            id='daily_digest',
            replace_existing=True
        )
        self.scheduler.start()
        logger.info("Scheduler started - daily digest will be sent at 08:00")

    async def run(self):
        await self.initialize()
        self.start_scheduler()
        
        logger.info("Starting Ezra bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.application.stop()
            self.scheduler.shutdown()


async def main():
    bot = EzraBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())