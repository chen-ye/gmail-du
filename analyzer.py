import pandas as pd
from rich.table import Table
from email.utils import parsedate_to_datetime

class GmailAnalyzer:
    def __init__(self, messages_data):
        self.df = self._prepare_dataframe(messages_data)

    def _prepare_dataframe(self, data):
        """Convert API response list to DataFrame."""
        records = []
        for msg in data:
            headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
            
            size = int(msg.get('sizeEstimate', 0))
            date_str = headers.get('Date')
            sender = headers.get('From', 'Unknown')
            
            # Parse date
            try:
                dt = parsedate_to_datetime(date_str) if date_str else None
            except:
                dt = None

            records.append({
                'id': msg['id'],
                'size': size,
                'sender': sender,
                'date': dt,
                'year_month': dt.strftime('%Y-%m') if dt else 'Unknown'
            })
            
        return pd.DataFrame(records)

    def summary(self):
        """Basic summary stats."""
        total_size = self.df['size'].sum()
        count = len(self.df)
        return count, total_size

    def group_by_sender(self, top_n=10):
        """Group usage by sender."""
        grouped = self.df.groupby('sender')['size'].sum().sort_values(ascending=False).head(top_n)
        return grouped

    def group_by_month(self):
        """Group usage by month."""
        grouped = self.df.groupby('year_month')['size'].sum().sort_index()
        return grouped
