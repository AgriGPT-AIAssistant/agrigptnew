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
        
        # 1. Setup Database fallback (PostgreSQL or SQLite)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "data", "chat_history.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Check for PostgreSQL availability via DATABASE_URL or PG_URI
        self.pg_uri = os.getenv("DATABASE_URL") or os.getenv("PG_URI")
        self.use_postgres = False
        self.param_style = "?"
        
        if self.pg_uri:
            try:
                import psycopg2
                # Test connection
                with psycopg2.connect(self.pg_uri) as conn:
                    pass
                self.use_postgres = True
                self.param_style = "%s"
                logger.info("MemoryManager configured to use PostgreSQL database")
            except Exception as e:
                logger.warning(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
                
        self._init_db()
        
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
                logger.warning(f"Failed to initialize MongoDB client: {e}. Using DB fallback.")
                self.mongo_client = None
        else:
            logger.info("No MONGO_URI configured or motor not installed. Using local/configured relational database fallback.")

    def _get_connection(self):
        """Returns a connection context manager for either SQLite or PostgreSQL."""
        if self.use_postgres:
            import psycopg2
            return psycopg2.connect(self.pg_uri)
        else:
            return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes PostgreSQL or SQLite database for persistent history with proper user_id support."""
        if self.use_postgres:
            try:
                import psycopg2
                with self._get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS sessions (
                                session_id VARCHAR(255) PRIMARY KEY,
                                user_id VARCHAR(255),
                                title VARCHAR(255),
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS messages (
                                id SERIAL PRIMARY KEY,
                                session_id VARCHAR(255),
                                user_id VARCHAR(255),
                                role VARCHAR(50),
                                content TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                            )
                        ''')
                logger.info("PostgreSQL database tables initialized successfully")
                return
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL database: {e}. Falling back to SQLite.")
                self.use_postgres = False
                self.param_style = "?"

        # SQLite fallback initialization
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT,
                        title TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        user_id TEXT,
                        role TEXT,
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                # Check if user_id column exists in sessions, if not, add it
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(sessions)")
                columns = [info[1] for info in cursor.fetchall()]
                if "user_id" not in columns:
                    conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
                    
                # Check if user_id column exists in messages, if not, add it
                cursor.execute("PRAGMA table_info(messages)")
                columns = [info[1] for info in cursor.fetchall()]
                if "user_id" not in columns:
                    conn.execute("ALTER TABLE messages ADD COLUMN user_id TEXT")
            logger.info("SQLite database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")

    async def get_history(self, session_id: str, user_id: str = "dev-user") -> List[Dict[str, str]]:
        """Retrieve recent conversation history for a given session, isolated by user_id."""
        if not session_id:
            return []

        # Enforce strict ownership check if the session already exists
        if self.mongo_client:
            try:
                session_doc = await self.sessions_col.find_one({"session_id": session_id})
                if session_doc and session_doc.get("user_id") != user_id:
                    raise PermissionError("Access denied to conversation session.")
            except PermissionError:
                raise
            except Exception as e:
                logger.warning(f"MongoDB ownership check failed: {e}")
        else:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"SELECT user_id FROM sessions WHERE session_id = {self.param_style}", 
                        (session_id,)
                    )
                    row = cursor.fetchone()
                    if row and row[0] != user_id:
                        raise PermissionError("Access denied to conversation session.")
            except PermissionError:
                raise
            except Exception as e:
                logger.warning(f"Database ownership check failed: {e}")

        # MongoDB Route
        if self.mongo_client:
            try:
                cursor = self.messages_col.find({"session_id": session_id, "user_id": user_id}).sort("created_at", 1)
                messages = await cursor.to_list(length=100)
                history = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
                return history[-(self.max_history * 2):] if history else []
            except Exception as e:
                logger.warning(f"MongoDB get_history failed for {session_id}: {e}")
                
        # Relational Database fallback (PostgreSQL or SQLite)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT role, content FROM messages WHERE session_id = {self.param_style} AND user_id = {self.param_style} ORDER BY id ASC", 
                    (session_id, user_id)
                )
                rows = cursor.fetchall()
                history = [{"role": row[0], "content": row[1]} for row in rows]
                return history[-(self.max_history * 2):] if history else []
        except Exception as e:
            logger.error(f"Database get_history failed for {session_id}: {e}")
            return []

    async def get_sessions(self, user_id: str = "dev-user") -> List[Dict[str, str]]:
        """Retrieve a list of all active sessions and their titles, isolated by user_id."""
        # MongoDB Route
        if self.mongo_client:
            try:
                cursor = self.sessions_col.find({"user_id": user_id}).sort("updated_at", -1)
                sessions = await cursor.to_list(length=100)
                return [{"session_id": s["session_id"], "title": s.get("title", "New Chat")} for s in sessions]
            except Exception as e:
                logger.warning(f"MongoDB get_sessions failed: {e}")
                
        # Relational Database fallback (PostgreSQL or SQLite)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT session_id, title FROM sessions WHERE user_id = {self.param_style} ORDER BY updated_at DESC", 
                    (user_id,)
                )
                rows = cursor.fetchall()
                return [{"session_id": row[0], "title": row[1]} for row in rows]
        except Exception as e:
            logger.error(f"Database get_sessions failed: {e}")
            return []

    async def add_interaction(self, session_id: str, user_message: str, assistant_message: str, user_id: str = "dev-user"):
        """Append a user-assistant interaction pair to the memory, isolated by user_id."""
        if not session_id:
            return

        title = user_message[:50]
        now = datetime.datetime.utcnow()

        # MongoDB Route
        if self.mongo_client:
            try:
                # Upsert session
                await self.sessions_col.update_one(
                    {"session_id": session_id, "user_id": user_id},
                    {"$set": {"updated_at": now}, "$setOnInsert": {"title": title}},
                    upsert=True
                )
                
                # Insert messages
                await self.messages_col.insert_many([
                    {"session_id": session_id, "user_id": user_id, "role": "user", "content": user_message, "created_at": now},
                    {"session_id": session_id, "user_id": user_id, "role": "assistant", "content": assistant_message, "created_at": now + datetime.timedelta(milliseconds=10)}
                ])
                
                # Enforce max history in MongoDB
                count = await self.messages_col.count_documents({"session_id": session_id, "user_id": user_id})
                max_msgs = self.max_history * 2
                if count > max_msgs:
                    excess = count - max_msgs
                    old_docs = await self.messages_col.find({"session_id": session_id, "user_id": user_id}).sort("created_at", 1).limit(excess).to_list(length=excess)
                    old_ids = [doc["_id"] for doc in old_docs]
                    await self.messages_col.delete_many({"_id": {"$in": old_ids}})
                    
                return
            except Exception as e:
                logger.warning(f"MongoDB add_interaction failed for {session_id}: {e}")

        # Database fallback logic (PostgreSQL or SQLite)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT session_id FROM sessions WHERE session_id = {self.param_style} AND user_id = {self.param_style}", 
                    (session_id, user_id)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        f"INSERT INTO sessions (session_id, user_id, title) VALUES ({self.param_style}, {self.param_style}, {self.param_style})", 
                        (session_id, user_id, title)
                    )
                else:
                    cursor.execute(
                        f"UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = {self.param_style} AND user_id = {self.param_style}", 
                        (session_id, user_id)
                    )
                    
                cursor.execute(
                    f"INSERT INTO messages (session_id, user_id, role, content) VALUES ({self.param_style}, {self.param_style}, {self.param_style}, {self.param_style})",
                    (session_id, user_id, "user", user_message)
                )
                cursor.execute(
                    f"INSERT INTO messages (session_id, user_id, role, content) VALUES ({self.param_style}, {self.param_style}, {self.param_style}, {self.param_style})",
                    (session_id, user_id, "assistant", assistant_message)
                )
                
                # Enforce max history
                cursor.execute(
                    f"SELECT id FROM messages WHERE session_id = {self.param_style} AND user_id = {self.param_style} ORDER BY id DESC", 
                    (session_id, user_id)
                )
                rows = cursor.fetchall()
                if len(rows) > self.max_history * 2:
                    keep_ids = [row[0] for row in rows[:self.max_history * 2]]
                    min_keep_id = min(keep_ids)
                    cursor.execute(
                        f"DELETE FROM messages WHERE session_id = {self.param_style} AND user_id = {self.param_style} AND id < {self.param_style}", 
                        (session_id, user_id, min_keep_id)
                    )
        except Exception as e:
            logger.error(f"Database add_interaction failed for {session_id}: {e}")
