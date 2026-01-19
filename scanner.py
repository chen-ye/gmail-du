from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from rich.progress import Progress
import math

class GmailScanner:
    def __init__(self, service):
        self.service = service

    def list_messages(self, query='', limit=None):
        """List messages matching query, up to limit."""
        messages = []
        request = self.service.users().messages().list(userId='me', q=query, includeSpamTrash=False)
        
        while request is not None:
            response = request.execute()
            batch = response.get('messages', [])
            messages.extend(batch)
            
            if limit and len(messages) >= limit:
                return messages[:limit]
                
            request = self.service.users().messages().list_next(request, response)
        
        return messages

    def get_message_details(self, message_ids, batch_size=50):
        """
        Fetch details using batch requests.
        """
        results = []
        
        def callback(request_id, response, exception):
            if exception:
                # Handle specific errors if needed
                print(f"Error fetching message {request_id}: {exception}")
            else:
                results.append(response)

        # Split into chunks
        total = len(message_ids)
        chunks = [message_ids[i:i + batch_size] for i in range(0, total, batch_size)]
        
        with Progress() as progress:
            task = progress.add_task("[green]Fetching details...", total=total)
            
            for chunk in chunks:
                batch = self.service.new_batch_http_request(callback=callback)
                for mid in chunk:
                    # format='metadata' gives us headers (Sender, Subject, Date) and sizeEstimate
                    # We need metadataHeaders to limit payload size if we only want specific headers
                    batch.add(
                        self.service.users().messages().get(
                            userId='me', 
                            id=mid, 
                            format='metadata',
                            metadataHeaders=['From', 'Date', 'Subject']
                        ),
                        request_id=mid
                    )
                batch.execute()
                progress.update(task, advance=len(chunk))
                
        return results

    def get_labels(self):
        """Fetch label ID to name mapping."""
        try:
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            return {l['id']: l['name'] for l in labels}
        except Exception:
            return {}

