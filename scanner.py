import asyncio
from typing import Any, Dict, List, Optional

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from storage import Storage

# Limit concurrency to avoid hitting rate limits too hard
MAX_CONCURRENT_REQUESTS = 30


class AsyncGmailScanner:
    def __init__(self, credentials: Credentials, storage: Storage) -> None:
        self.creds = credentials
        self.storage = storage
        self.base_url = "https://gmail.googleapis.com/gmail/v1/users/me"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.creds.token}",
                    "Accept": "application/json",
                }
            )

        # Check token expiry and refresh if needed
        if self.creds.expired:
            self.creds.refresh(Request())
            if self.session:
                self.session.headers["Authorization"] = f"Bearer {self.creds.token}"

        assert self.session is not None
        return self.session

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def fetch_list(self, query: str = "", limit: Optional[int] = None) -> None:
        """
        Fetch message list pages and save IDs to DB.
        """
        session = await self._get_session()
        next_page_token = await self.storage.get_state("next_page_token")

        params = {"q": query, "maxResults": "500", "includeSpamTrash": "false"}

        total_fetched = 0

        print("Scanning message list...")
        while True:
            if next_page_token:
                params["pageToken"] = next_page_token

            async with session.get(f"{self.base_url}/messages", params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"Error listing messages: {resp.status} - {text}")
                    break

                data = await resp.json()
                messages = data.get("messages", [])

                if messages:
                    await self.storage.save_messages_batch(messages)
                    total_fetched += len(messages)
                    print(f"Found {len(messages)} messages (Total: {total_fetched})...")

                next_page_token = data.get("nextPageToken")
                await self.storage.save_state(
                    "next_page_token", next_page_token if next_page_token else ""
                )

                if not next_page_token:
                    break

                if limit and total_fetched >= limit:
                    break

    async def fetch_details(self) -> int:
        """
        Fetch details for pending messages.
        """
        session = await self._get_session()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        pending_ids = await self.storage.get_pending_messages(limit=5000)
        if not pending_ids:
            return 0

        async def get_msg(mid: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    url = f"{self.base_url}/messages/{mid}"
                    params = {
                        "format": "metadata",
                        "metadataHeaders": ["From", "Date", "Subject"],
                    }
                    async with session.get(url, params=params) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status == 404:
                            return {"id": mid, "deleted": True}
                        else:
                            return None
                except Exception:
                    return None

        results: List[Dict[str, Any]] = []
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(
                "[cyan]Fetching details...", total=len(pending_ids)
            )

            tasks = [get_msg(mid) for mid in pending_ids]

            for coro in asyncio.as_completed(tasks):
                res = await coro
                progress.update(task, advance=1)
                if res:
                    if not res.get("deleted"):
                        payload = res.get("payload", {})
                        headers = {
                            h["name"]: h["value"] for h in payload.get("headers", [])
                        }

                        results.append(
                            {
                                "id": res["id"],
                                "size": int(res.get("sizeEstimate", 0)),
                                "internalDate": int(res.get("internalDate", 0)),
                                "sender": headers.get("From", "Unknown"),
                                "subject": headers.get("Subject", "(No Subject)"),
                            }
                        )

                if len(results) >= 100:
                    await self.storage.update_message_details(results)
                    results = []

            if results:
                await self.storage.update_message_details(results)

        return len(pending_ids)

    async def ensure_label(self, name: str) -> str:
        """Get label ID by name, creating if it doesn't exist."""
        session = await self._get_session()

        # 1. List labels to see if it exists
        async with session.get(f"{self.base_url}/labels") as resp:
            data = await resp.json()
            labels = data.get("labels", [])
            for label in labels:
                if label["name"].lower() == name.lower():
                    return str(label["id"])

        # 2. Create if not found
        payload = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        async with session.post(f"{self.base_url}/labels", json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return str(data["id"])
            else:
                text = await resp.text()
                raise Exception(f"Failed to create label: {text}")

    async def add_labels(
        self, message_ids: List[str], label_name: str = "gmail-du-marked"
    ) -> int:
        """Apply label to a list of message IDs."""
        if not message_ids:
            return 0

        try:
            label_id = await self.ensure_label(label_name)
            session = await self._get_session()

            chunk_size = 1000
            total_modified = 0

            for i in range(0, len(message_ids), chunk_size):
                chunk = message_ids[i : i + chunk_size]
                payload = {"ids": chunk, "addLabelIds": [label_id]}

                async with session.post(
                    f"{self.base_url}/messages/batchModify", json=payload
                ) as resp:
                    if resp.status == 200:
                        total_modified += len(chunk)
                    else:
                        print(f"Error modifying batch: {await resp.text()}")

            return total_modified

        except Exception as e:
            print(f"Error adding labels: {e}")
            raise

