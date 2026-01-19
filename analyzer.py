import datetime
from typing import Any, List, Tuple

import pandas as pd


class GmailAnalyzer:
    def __init__(self, db_rows: List[Any]) -> None:
        self.df = self._prepare_dataframe(db_rows)

    def _prepare_dataframe(self, rows: List[Any]) -> pd.DataFrame:
        """Convert DB rows to DataFrame."""
        if not rows:
            return pd.DataFrame(columns=["id", "size", "sender", "date", "year_month"])

        data = []
        for row in rows:
            # row is aiosqlite.Row/tuple: id, thread_id, size, internal_date, ...
            # Check indices based on SELECT * FROM messages
            # Schema: id, thread_id, size, internal_date, sender, subject, status

            # internal_date is ms timestamp
            ts = row["internal_date"]
            dt = datetime.datetime.fromtimestamp(ts / 1000) if ts else None

            data.append(
                {
                    "id": row["id"],
                    "size": row["size"],
                    "sender": row["sender"],
                    "subject": row["subject"],
                    "date": dt,
                    "year_month": dt.strftime("%Y-%m") if dt else "Unknown",
                }
            )

        return pd.DataFrame(data)

    def summary(self) -> Tuple[int, int]:
        """Basic summary stats."""
        if self.df.empty:
            return 0, 0
        total_size = int(self.df["size"].sum())
        count = len(self.df)
        return count, total_size

    def group_by_sender(self, top_n: int = 10) -> pd.Series:
        """Group usage by sender."""
        if self.df.empty:
            return pd.Series()
        grouped = (
            self.df.groupby("sender")["size"]
            .sum()
            .sort_values(ascending=False)
            .head(top_n)
        )
        return grouped

    def group_by_month(self) -> pd.Series:
        """Group usage by month."""
        if self.df.empty:
            return pd.Series()
        grouped = self.df.groupby("year_month")["size"].sum().sort_index()
        return grouped

