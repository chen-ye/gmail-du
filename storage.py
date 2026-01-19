from typing import Any

import aiosqlite

DB_NAME = "gmail_du.db"


class Storage:
    def __init__(self, db_path: str = DB_NAME) -> None:
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if not self.db:
            self.db = await aiosqlite.connect(self.db_path)
            self.db.row_factory = aiosqlite.Row

    async def close(self) -> None:
        if self.db:
            await self.db.close()
            self.db = None

    async def init_db(self) -> None:
        await self.connect()
        assert self.db is not None
        await self.db.execute("""
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
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await self.db.commit()

    async def get_state(self, key: str) -> str | None:
        if not self.db:
            await self.connect()
        assert self.db is not None
        async with self.db.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def save_state(self, key: str, value: str) -> None:
        if not self.db:
            await self.connect()
        assert self.db is not None
        await self.db.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value)
        )
        await self.db.commit()

    async def save_messages_batch(self, messages: list[dict[str, Any]]) -> None:
        """
        Save a batch of message IDs.
        messages: list of dicts with 'id' and 'threadId'.
        """
        if not self.db:
            await self.connect()
        assert self.db is not None
        # parsing 'pending' status is default
        await self.db.executemany(
            "INSERT OR IGNORE INTO messages (id, thread_id) VALUES (?, ?)",
            [(m["id"], m["threadId"]) for m in messages],
        )
        await self.db.commit()

    async def update_message_details(self, details_list: list[dict[str, Any]]) -> None:
        """
        Update message details after fetching.
        details_list: list of tuples/dicts matching the schema
        """
        if not self.db:
            await self.connect()
        assert self.db is not None
        await self.db.executemany(
            """
            UPDATE messages
            SET size = ?, internal_date = ?, sender = ?, subject = ?,
            status = 'complete'
            WHERE id = ?
            """,
            [
                (d["size"], d["internalDate"], d["sender"], d["subject"], d["id"])
                for d in details_list
            ],
        )
        await self.db.commit()

    async def get_pending_messages(self, limit: int = 1000) -> list[str]:
        if not self.db:
            await self.connect()
        assert self.db is not None
        async with self.db.execute(
            "SELECT id FROM messages WHERE status = 'pending' LIMIT ?", (limit,)
        ) as cursor:
            return [str(row["id"]) for row in await cursor.fetchall()]

    async def get_all_completed_messages(self) -> list[Any]:
        if not self.db:
            await self.connect()
        assert self.db is not None
        async with self.db.execute(
            "SELECT * FROM messages WHERE status = 'complete'"
        ) as cursor:
            rows = await cursor.fetchall()
            return list(rows)

    async def get_total_counts(self) -> tuple[int, int]:
        if not self.db:
            await self.connect()
        assert self.db is not None
        async with self.db.execute(
            "SELECT COUNT(*), COUNT(CASE WHEN status='complete' THEN 1 END) "
            "FROM messages"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return int(row[0]), int(row[1])
            return 0, 0
