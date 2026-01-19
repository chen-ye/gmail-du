
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

DB_NAME = "gmail_du.db"


class Storage:
    def __init__(self, db_path: str = DB_NAME) -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    size INTEGER,
                    internal_date INTEGER,
                    sender TEXT,
                    subject TEXT,
                    status TEXT DEFAULT 'pending'
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await db.commit()

    async def get_state(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM state WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return str(row[0]) if row else None

    async def save_state(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value)
            )
            await db.commit()

    async def save_messages_batch(self, messages: List[Dict[str, Any]]) -> None:
        """
        Save a batch of message IDs.
        messages: list of dicts with 'id' and 'threadId'.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # parsing 'pending' status is default
            await db.executemany(
                "INSERT OR IGNORE INTO messages (id, thread_id) VALUES (?, ?)",
                [(m["id"], m["threadId"]) for m in messages],
            )
            await db.commit()

    async def update_message_details(self, details_list: List[Dict[str, Any]]) -> None:
        """
        Update message details after fetching.
        details_list: list of tuples/dicts matching the schema
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                UPDATE messages
                SET size = ?, internal_date = ?, sender = ?, subject = ?, status = 'complete'
                WHERE id = ?
                """,
                [
                    (d["size"], d["internalDate"], d["sender"], d["subject"], d["id"])
                    for d in details_list
                ],
            )
            await db.commit()

    async def get_pending_messages(self, limit: int = 1000) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id FROM messages WHERE status = 'pending' LIMIT ?", (limit,)
            ) as cursor:
                return [str(row["id"]) for row in await cursor.fetchall()]

    async def get_all_completed_messages(self) -> List[Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM messages WHERE status = 'complete'"
            ) as cursor:
                return await cursor.fetchall()


    async def get_total_counts(self) -> Tuple[int, int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*), COUNT(CASE WHEN status='complete' THEN 1 END) "
                "FROM messages"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return int(row[0]), int(row[1])
                return 0, 0

