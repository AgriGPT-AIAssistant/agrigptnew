import json
import logging
import sqlite3
import os
from typing import List, Dict

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.core.config import settings

logger = logging.getLogger("agrigpt.services.memory_manager")

class MemoryManager:
    """
    Manages conversational memory using Redis for persistence, with a
    proper SQLite database fallback if Redis is unavailable or not configured.
    """
    def __init__(self, max_history: int = 6):
        self.max_history = max_history
        self.redis_client = None
        
        # Setup SQLite Database fallback for persistent storage
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "data", "chat_history.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_sqlite_db()
        
        # Check if Redis URL is configured and redis is installed
        redis_url = getattr(settings, "REDIS_URL", None)
        if redis and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                logger.info(f"MemoryManager initialized with Redis at {redis_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client: {e}. Using SQLite fallback.")
                self.redis_client = None
        else:
            logger.info("No REDIS_URL configured or redis not installed. Using SQLite fallback database.")

    def _init_sqlite_db(self):
        """Initializes the local SQLite database for persistent history fallback."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        title TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        role TEXT,
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")

    async def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Retrieve recent conversation history for a given session."""
        if not session_id:
            return []

        if self.redis_client:
            try:
                key = f"session:{session_id}:memory"
                data = await self.redis_client.lrange(key, 0, -1)
                history = [json.loads(item) for item in data]
                return history
            except Exception as e:
                logger.warning(f"Redis get_history failed for {session_id}: {e}")
                
        # SQLite Database fallback
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", 
                    (session_id,)
                )
                rows = cursor.fetchall()
                history = [{"role": row[0], "content": row[1]} for row in rows]
                return history[-(self.max_history * 2):] if history else []
        except Exception as e:
            logger.error(f"SQLite get_history failed for {session_id}: {e}")
            return []

    async def get_sessions(self) -> List[Dict[str, str]]:
        """Retrieve a list of all active sessions and their first message."""
        sessions = []
        if self.redis_client:
            try:
                keys = await self.redis_client.keys("session:*:memory")
                for key in keys:
                    session_id = key.split(":")[1]
                    first_msg_str = await self.redis_client.lindex(key, 0)
                    title = "New Chat"
                    if first_msg_str:
                        try:
                            msg = json.loads(first_msg_str)
                            title = msg.get("content", "New Chat")[:50]
                        except:
                            pass
                    sessions.append({"session_id": session_id, "title": title})
                return sessions
            except Exception as e:
                logger.warning(f"Redis get_sessions failed: {e}")
                
        # SQLite Database fallback
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT session_id, title FROM sessions ORDER BY updated_at DESC")
                rows = cursor.fetchall()
                return [{"session_id": row[0], "title": row[1]} for row in rows]
        except Exception as e:
            logger.error(f"SQLite get_sessions failed: {e}")
            return []

    async def add_interaction(self, session_id: str, user_message: str, assistant_message: str):
        """Append a user-assistant interaction pair to the memory."""
        if not session_id:
            return

        user_entry = {"role": "user", "content": user_message}
        assistant_entry = {"role": "assistant", "content": assistant_message}
        
        if self.redis_client:
            try:
                key = f"session:{session_id}:memory"
                # Store the new messages
                await self.redis_client.rpush(key, json.dumps(user_entry))
                await self.redis_client.rpush(key, json.dumps(assistant_entry))
                
                # Trim the history to max_history (multiply by 2 because each interaction has 2 messages)
                await self.redis_client.ltrim(key, -(self.max_history * 2), -1)
                
                # Set an expiry for the session memory (e.g., 24 hours)
                await self.redis_client.expire(key, 86400)
                return
            except Exception as e:
                logger.warning(f"Redis add_interaction failed for {session_id}: {e}")

        # SQLite Database fallback logic
        try:
            title = user_message[:50]
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
                if not cursor.fetchone():
                    conn.execute("INSERT INTO sessions (session_id, title) VALUES (?, ?)", (session_id, title))
                else:
                    conn.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
                    
                conn.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "user", user_message)
                )
                conn.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "assistant", assistant_message)
                )
                
                # Enforce max history
                cursor.execute("SELECT id FROM messages WHERE session_id = ? ORDER BY id DESC", (session_id,))
                rows = cursor.fetchall()
                if len(rows) > self.max_history * 2:
                    keep_ids = [row[0] for row in rows[:self.max_history * 2]]
                    min_keep_id = min(keep_ids)
                    conn.execute("DELETE FROM messages WHERE session_id = ? AND id < ?", (session_id, min_keep_id))
        except Exception as e:
            logger.error(f"SQLite add_interaction failed for {session_id}: {e}")
