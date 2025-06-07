import os
import asyncio
import logging
import hashlib
from typing import List
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import DialogFilterDefault
from dotenv import load_dotenv

from database import Database

# Load environment variables
load_dotenv('config/credentials.env')

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class EzraUserbot:
    def __init__(self):
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.phone = os.getenv("TELEGRAM_PHONE_NUMBER")
        self.folder_name = os.getenv("TELEGRAM_FOLDER_NAME", "AI")  # Default to "AI"
        self.session_file = "/app/config/userbot.session"
        
        if not all([self.api_id, self.api_hash, self.phone]):
            raise ValueError("Missing required Telegram API credentials in config/credentials.env")
        
        logger.info(f"Using Telegram folder: '{self.folder_name}'")
        self.client = TelegramClient(self.session_file, int(self.api_id), self.api_hash)
        self.db = Database()

    async def initialize(self):
        """Initialize database and Telegram client"""
        await self.db.init_db()
        logger.info("Database initialized")
        
        # Connect to Telegram (non-interactive, using saved session)
        await self.client.start(phone=self.phone)
        logger.info("Userbot connected to Telegram")
        
        # Get user info
        me = await self.client.get_me()
        logger.info(f"Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'no username'})")

    async def find_target_folder_chats(self) -> List[int]:
        """Find all chats in the configured folder ONLY"""
        target_chats = []
        
        try:
            # Get all dialog filters (folders)
            result = await self.client(GetDialogFiltersRequest())
            logger.info(f"Found {len(result.filters)} total folders")
            
            # Debug: list all folder names
            for i, dialog_filter in enumerate(result.filters):
                if hasattr(dialog_filter, 'title'):
                    if hasattr(dialog_filter.title, 'text'):
                        folder_name = dialog_filter.title.text
                    else:
                        folder_name = str(dialog_filter.title)
                else:
                    folder_name = f'Folder {i}'
                logger.info(f"Folder {i}: '{folder_name}'")
            
            target_folder = None
            for dialog_filter in result.filters:
                if hasattr(dialog_filter, 'title'):
                    # Handle both string and TextWithEntities objects
                    if hasattr(dialog_filter.title, 'text'):
                        title = dialog_filter.title.text.strip()
                    else:
                        title = str(dialog_filter.title).strip()
                    
                    logger.info(f"Checking folder: '{title}' (lowercase: '{title.lower()}')")
                    if title.lower() == self.folder_name.lower():
                        target_folder = dialog_filter
                        logger.info(f"✅ Found target folder '{self.folder_name}' with {len(dialog_filter.include_peers)} chats")
                        break
            
            if target_folder:
                # Get chats from target folder
                for peer in target_folder.include_peers:
                    try:
                        entity = await self.client.get_entity(peer)
                        target_chats.append(entity.id)
                        chat_name = getattr(entity, 'title', getattr(entity, 'first_name', f'Chat {entity.id}'))
                        logger.info(f"✅ Added folder chat: {chat_name} (ID: {entity.id})")
                    except Exception as e:
                        logger.error(f"❌ Error getting entity for peer {peer}: {e}")
            else:
                logger.error(f"❌ Folder '{self.folder_name}' not found! Available folders listed above.")
                logger.error(f"❌ Make sure you have a folder named exactly '{self.folder_name}' in Telegram")
                logger.error(f"❌ You can change the folder name with TELEGRAM_FOLDER_NAME environment variable")
                logger.error("❌ NO CHATS WILL BE PROCESSED")
                return []  # Return empty list instead of fallback
                
        except Exception as e:
            logger.error(f"❌ Error getting dialog filters: {e}")
            logger.error("❌ Cannot access folders - NO CHATS WILL BE PROCESSED")
            return []  # Return empty list instead of fallback
            
        logger.info(f"✅ Found {len(target_chats)} chats in '{self.folder_name}' folder to process")
        return target_chats

    async def fetch_recent_messages(self, chat_id: int, limit: int = 10) -> int:
        """Fetch recent messages from a specific chat"""
        messages_saved = 0
        
        try:
            # Get chat info for logging
            entity = await self.client.get_entity(chat_id)
            chat_name = getattr(entity, 'title', getattr(entity, 'first_name', f'Chat {chat_id}'))
            chat_username = getattr(entity, 'username', None)
            
            logger.info(f"Fetching last {limit} messages from {chat_name} (@{chat_username})")
            
            # Get recent messages
            async for message in self.client.iter_messages(entity, limit=limit):
                if not message.message:  # Skip messages without text content
                    continue
                
                # Create content hash
                content_hash = hashlib.md5(message.message.encode()).hexdigest()
                
                # Build message link if possible
                message_link = None
                if chat_username and message.id:
                    # Public channel with username
                    message_link = f"https://t.me/{chat_username}/{message.id}"
                    logger.info(f"Built public link: {message_link}")
                elif message.id and chat_id < 0:
                    # Private channel/group - use c/ format with channel ID
                    # Remove the -100 prefix that Telegram adds to channel IDs
                    channel_id_str = str(abs(chat_id))
                    if channel_id_str.startswith('100'):
                        channel_id_str = channel_id_str[3:]  # Remove '100' prefix
                    message_link = f"https://t.me/c/{channel_id_str}/{message.id}"
                    logger.info(f"Built private link: {message_link}")
                else:
                    logger.info(f"No link possible - username: {chat_username}, msg_id: {message.id}, chat_id: {chat_id}")
                
                # Try to save to database
                logger.info(f"Attempting to save with link: {message_link}")
                success = await self.db.add_message(
                    chat_id, message.message, message.date, content_hash, source='userbot', message_link=message_link
                )
                
                if success:
                    messages_saved += 1
                    logger.info(f"✅ Saved new message from {chat_name}: {message.message[:50]}...")
                else:
                    logger.info(f"❌ Failed to save message from {chat_name} (likely duplicate)")
            
        except Exception as e:
            logger.error(f"Error fetching messages from chat {chat_id}: {e}")
        
        return messages_saved

    async def run_batch(self):
        """Run batch job: fetch recent messages and exit"""
        total_messages_saved = 0
        
        try:
            await self.initialize()
            
            # Find target folder chats
            target_chats = await self.find_target_folder_chats()
            
            if not target_chats:
                logger.info(f"No chats found in '{self.folder_name}' folder, exiting")
                return
            
            # Process each chat
            for chat_id in target_chats:
                try:
                    messages_saved = await self.fetch_recent_messages(chat_id, limit=10)
                    total_messages_saved += messages_saved
                    
                    # Small delay between chats to avoid rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing chat {chat_id}: {e}")
                    continue
            
            logger.info(f"Batch job completed. Saved {total_messages_saved} new messages from {len(target_chats)} chats in '{self.folder_name}' folder")
            
        except Exception as e:
            logger.error(f"Error in batch job: {e}")
            raise
        finally:
            if self.client.is_connected():
                await self.client.disconnect()
                logger.info("Disconnected from Telegram")


async def main():
    userbot = EzraUserbot()
    await userbot.run_batch()


if __name__ == "__main__":
    asyncio.run(main())