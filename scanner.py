import aiohttp
import asyncio
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from google.auth.transport.requests import Request
import logging

# Limit concurrency to avoid hitting rate limits too hard
# Gmail API User Rate Limit: 250 quota units / user / second
# messages.get = 5 units. 
# 250 / 5 = 50 requests per second max.
MAX_CONCURRENT_REQUESTS = 30

class AsyncGmailScanner:
    def __init__(self, credentials, storage):
        self.creds = credentials
        self.storage = storage
        self.base_url = "https://gmail.googleapis.com/gmail/v1/users/me"
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers={
                "Authorization": f"Bearer {self.creds.token}",
                "Accept": "application/json"
            })
        
        # Check token expiry and refresh if needed
        if self.creds.expired:
            self.creds.refresh(Request())
            self.session.headers["Authorization"] = f"Bearer {self.creds.token}"
            
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()

    async def fetch_list(self, query='', limit=None):
        """
        Fetch message list pages and save IDs to DB.
        """
        session = await self._get_session()
        
        # Check if we have a saved page token for this query
        # Note: Ideally we key state by query, but for MVP we use a global 'list_page_token'
        # If the query changes, the user might want to clear DB or we need smart state management.
        # For now, we'll assume one active query session.
        next_page_token = await self.storage.get_state("next_page_token")
        
        params = {
            "q": query,
            "maxResults": "500", # Max allowed
            "includeSpamTrash": "false"
        }

        total_fetched = 0
        
        # If we have a limit, check if we already have enough in DB? 
        # For now, let's keep fetching until we hit limit or end.
        
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
                await self.storage.save_state("next_page_token", next_page_token if next_page_token else "")
                
                if not next_page_token:
                    break
                
                if limit and total_fetched >= limit:
                    break

    async def fetch_details(self):
        """
        Fetch details for pending messages.
        """
        session = await self._get_session()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        
        pending_ids = await self.storage.get_pending_messages(limit=5000) # Process in chunks
        if not pending_ids:
            return 0

        async def get_msg(mid):
            async with semaphore:
                try:
                    # format='metadata' is lighter, 'minimal' is lightest but has no headers
                    url = f"{self.base_url}/messages/{mid}"
                    params = {
                        "format": "metadata",
                        "metadataHeaders": ["From", "Date", "Subject"]
                    }
                    async with session.get(url, params=params) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        elif resp.status == 404:
                            # Message deleted?
                            return {"id": mid, "deleted": True}
                        else:
                            # Rate limit or other error
                            return None
                except Exception as e:
                    return None

        # Process
        results = []
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Fetching details...", total=len(pending_ids))
            
            # Create tasks
            tasks = [get_msg(mid) for mid in pending_ids]
            
            # Run tasks
            for coro in asyncio.as_completed(tasks):
                res = await coro
                progress.update(task, advance=1)
                if res:
                    if res.get("deleted"):
                         # Mark deleted or remove? For now, we just don't add to update list
                         # Maybe mark status='deleted' in DB
                         pass
                    else:
                        payload = res.get("payload", {})
                        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
                        
                        results.append({
                            "id": res["id"],
                            "size": int(res.get("sizeEstimate", 0)),
                            "internalDate": int(res.get("internalDate", 0)),
                            "sender": headers.get("From", "Unknown"),
                            "subject": headers.get("Subject", "(No Subject)")
                        })
                        
                # Batch save every 100 to avoid memory bloat
                if len(results) >= 100:
                    await self.storage.update_message_details(results)
                    results = []

            # Save remaining
            if results:
                await self.storage.update_message_details(results)
                
        return len(pending_ids)
