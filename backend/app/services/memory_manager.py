import json
import logging
import sqlite3
import os
import datetime
from typing import List, Dict

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None

from app.core.config import settings

logger = logging.getLogger("agrigpt.services.memory_manager")

class MemoryManager:
    """
    Manages conversational memory using MongoDB for cloud persistence, 
    with a proper SQLite database fallback if MongoDB is not configured.
    """
    def __init__(self, max_history: int = 6):
        self.max_history = max_history
        self.mongo_client = None
        self.db = None
        self.sessions_col = None
        self.messages_col = None
        
        # 1. Setup SQLite Database fallback for local persistent storage
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "data", "chat_history.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_sqlite_db()
        
        # 2. Check if MONGO_URI is configured and motor is installed
        mongo_uri = getattr(settings, "MONGO_URI", os.getenv("MONGO_URI"))
        if AsyncIOMotorClient and mongo_uri:
            try:
                self.mongo_client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
                self.db = self.mongo_client.agrigpt
                self.sessions_col = self.db.sessions
                self.messages_col = self.db.messages
                logger.info(f"MemoryManager initialized with MongoDB Atlas")
            except Exception as e:
                logger.warning(f"Failed to initialize MongoDB client: {e}. Using SQLite fallback.")
                self.mongo_client = None
        else:
            logger.info("No MONGO_URI configured or motor not installed. Using local SQLite database.")

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

        # MongoDB Route
        if self.mongo_client:
            try:
                cursor = self.messages_col.find({"session_id": session_id}).sort("created_at", 1)
                messages = await cursor.to_list(length=100)
                history = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
                return history[-(self.max_history * 2):] if history else []
            except Exception as e:
                logger.warning(f"MongoDB get_history failed for {session_id}: {e}")
                
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
        """Retrieve a list of all active sessions and their titles."""
        # MongoDB Route
        if self.mongo_client:
            try:
                cursor = self.sessions_col.find({}).sort("updated_at", -1)
                sessions = await cursor.to_list(length=100)
                return [{"session_id": s["session_id"], "title": s.get("title", "New Chat")} for s in sessions]
            except Exception as e:
                logger.warning(f"MongoDB get_sessions failed: {e}")
                
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

        title = user_message[:50]
        now = datetime.datetime.utcnow()

        # MongoDB Route
        if self.mongo_client:
            try:
                # Upsert session
                await self.sessions_col.update_one(
                    {"session_id": session_id},
                    {"$set": {"updated_at": now}, "$setOnInsert": {"title": title}},
                    upsert=True
                )
                
                # Insert messages
                await self.messages_col.insert_many([
                    {"session_id": session_id, "role": "user", "content": user_message, "created_at": now},
                    {"session_id": session_id, "role": "assistant", "content": assistant_message, "created_at": now + datetime.timedelta(milliseconds=10)}
                ])
                
                # Enforce max history in MongoDB
                count = await self.messages_col.count_documents({"session_id": session_id})
                max_msgs = self.max_history * 2
                if count > max_msgs:
                    excess = count - max_msgs
                    old_docs = await self.messages_col.find({"session_id": session_id}).sort("created_at", 1).limit(excess).to_list(length=excess)
                    old_ids = [doc["_id"] for doc in old_docs]
                    await self.messages_col.delete_many({"_id": {"$in": old_ids}})
                    
                return
            except Exception as e:
                logger.warning(f"MongoDB add_interaction failed for {session_id}: {e}")

        # SQLite Database fallback logic
        try:
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
