import os
import aiosqlite
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv("DATABASE_PATH", "ezra.db")
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    is_subscribed BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    channel_name TEXT,
                    channel_username TEXT,
                    added_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (added_by) REFERENCES users (user_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    content TEXT,
                    message_date TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE,
                    content_hash TEXT,
                    source TEXT DEFAULT 'bot',
                    message_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_id) REFERENCES channels (channel_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS digests (
                    digest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_content_hash ON messages (content_hash)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_processed ON messages (processed)
            """)
            
            await db.commit()

    async def add_user(self, user_id: int, username: str = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def subscribe_user(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "UPDATE users SET is_subscribed = TRUE WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def unsubscribe_user(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "UPDATE users SET is_subscribed = FALSE WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def get_subscribed_users(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id FROM users WHERE is_subscribed = TRUE"
            )
            result = await cursor.fetchall()
            return [row[0] for row in result]

    async def add_channel(self, channel_id: int, channel_name: str, channel_username: str, added_by: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO channels (channel_id, channel_name, channel_username, added_by) VALUES (?, ?, ?, ?)",
                    (channel_id, channel_name, channel_username, added_by)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def remove_channel(self, channel_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
                await db.commit()
                return True
            except Exception:
                return False

    async def get_channels(self) -> List[Tuple[int, str, str]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT channel_id, channel_name, channel_username FROM channels"
            )
            return await cursor.fetchall()

    async def add_message(self, channel_id: int, content: str, message_date: datetime, content_hash: str, source: str = 'bot', message_link: str = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM messages WHERE content_hash = ?",
                    (content_hash,)
                )
                count = (await cursor.fetchone())[0]
                
                if count > 0:
                    return False
                
                await db.execute(
                    "INSERT INTO messages (channel_id, content, message_date, content_hash, source, message_link) VALUES (?, ?, ?, ?, ?, ?)",
                    (channel_id, content, message_date, content_hash, source, message_link)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def get_unprocessed_messages(self) -> List[Tuple[int, str, datetime, str]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT message_id, content, message_date, message_link FROM messages WHERE processed = FALSE ORDER BY message_date DESC"
            )
            return await cursor.fetchall()

    async def mark_messages_processed(self, message_ids: List[int]) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                placeholders = ','.join('?' * len(message_ids))
                await db.execute(
                    f"UPDATE messages SET processed = TRUE WHERE message_id IN ({placeholders})",
                    message_ids
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def save_digest(self, date: str, content: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO digests (date, content) VALUES (?, ?)",
                    (date, content)
                )
                await db.commit()
                return True
            except Exception:
                return False

    async def get_latest_digest(self) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT content FROM digests ORDER BY created_at DESC LIMIT 1"
            )
            result = await cursor.fetchone()
            return result[0] if result else None