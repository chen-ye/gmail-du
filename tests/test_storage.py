
import pytest

from storage import Storage


@pytest.mark.asyncio
async def test_storage_lifecycle():
    storage = Storage(db_path=":memory:")
    assert storage.db is None

    await storage.connect()
    assert storage.db is not None

    await storage.close()
    assert storage.db is None


@pytest.mark.asyncio
async def test_storage_init_db():
    storage = Storage(db_path=":memory:")
    await storage.init_db()

    # Check tables created
    async with storage.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cursor:
        tables = await cursor.fetchall()
        table_names = [row["name"] for row in tables]
        assert "messages" in table_names
        assert "state" in table_names

    await storage.close()


@pytest.mark.asyncio
async def test_save_and_get_messages():
    storage = Storage(db_path=":memory:")
    await storage.init_db()

    messages = [
        {"id": "msg1", "threadId": "thread1"},
        {"id": "msg2", "threadId": "thread2"},
    ]

    await storage.save_messages_batch(messages)

    pending = await storage.get_pending_messages()
    assert len(pending) == 2
    assert "msg1" in pending
    assert "msg2" in pending

    # Update details
    details = [
        {
            "id": "msg1",
            "size": 1024,
            "internalDate": 123456789,
            "sender": "test@test.com",
            "subject": "Test Subject",
        }
    ]

    await storage.update_message_details(details)

    pending = await storage.get_pending_messages()
    assert len(pending) == 1
    assert pending[0] == "msg2"

    completed = await storage.get_all_completed_messages()
    assert len(completed) == 1
    row = completed[0]
    assert row["id"] == "msg1"
    assert row["size"] == 1024
    assert row["status"] == "complete"

    await storage.close()


@pytest.mark.asyncio
async def test_state():
    storage = Storage(db_path=":memory:")
    await storage.init_db()

    val = await storage.get_state("foo")
    assert val is None

    await storage.save_state("foo", "bar")
    val = await storage.get_state("foo")
    assert val == "bar"

    await storage.save_state("foo", "baz")
    val = await storage.get_state("foo")
    assert val == "baz"

    await storage.close()
