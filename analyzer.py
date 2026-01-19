import pandas as pd
from rich.table import Table
import datetime

class GmailAnalyzer:
    def __init__(self, db_rows):
        self.df = self._prepare_dataframe(db_rows)

    def _prepare_dataframe(self, rows):
        """Convert DB rows to DataFrame."""
        if not rows:
            return pd.DataFrame(columns=['id', 'size', 'sender', 'date', 'year_month'])

        data = []
        for row in rows:
            # row is aiosqlite.Row/tuple: id, thread_id, size, internal_date, sender, subject, status
            # Check indices based on SELECT * FROM messages
            # Schema: id, thread_id, size, internal_date, sender, subject, status
            
            # internal_date is ms timestamp
            ts = row['internal_date']
            dt = datetime.datetime.fromtimestamp(ts / 1000) if ts else None
            
            data.append({
                'id': row['id'],
                'size': row['size'],
                'sender': row['sender'],
                'date': dt,
                'year_month': dt.strftime('%Y-%m') if dt else 'Unknown'
            })
            
        return pd.DataFrame(data)

    def summary(self):
        """Basic summary stats."""
        if self.df.empty:
            return 0, 0
        total_size = self.df['size'].sum()
        count = len(self.df)
        return count, total_size

    def group_by_sender(self, top_n=10):
        """Group usage by sender."""
        if self.df.empty:
            return pd.Series()
        grouped = self.df.groupby('sender')['size'].sum().sort_values(ascending=False).head(top_n)
        return grouped

    def group_by_month(self):
        """Group usage by month."""
        if self.df.empty:
            return pd.Series()
        grouped = self.df.groupby('year_month')['size'].sum().sort_index()
        return grouped
