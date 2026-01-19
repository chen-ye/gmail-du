import asyncio

import pandas as pd
from google.oauth2.credentials import Credentials
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    Select,
    Static,
)
from textual.worker import Worker

from analyzer import GmailAnalyzer
from scanner import AsyncGmailScanner
from storage import Storage


class GmailDUApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    .top-bar {
        height: auto;
        dock: top;
        padding: 1;
        background: $boost;
    }

    .controls {
        height: auto;
        margin-bottom: 1;
        align-vertical: center;
    }

    Input {
        width: 40;
    }

    Button {
        margin-left: 1;
    }

    DataTable {
        height: 1fr;
        border: solid green;
    }

    #stats_display {
        margin-left: 2;
        color: $text;
        text-style: bold;
    }

    #scan_progress {
        width: 100%;
        margin-top: 1;
        display: none;
    }

    .progress-visible {
        display: block !important;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_data", "Refresh"),
        Binding("escape", "go_back", "Back"),
        Binding("m", "mark_selected", "Mark Selection in Gmail"),
    ]

    def __init__(self, storage: Storage, creds: Credentials) -> None:
        super().__init__()
        self.storage = storage
        self.creds = creds
        self.scanner: AsyncGmailScanner | None = None
        self.worker: Worker | None = None
        self.current_view: str = "Top Senders"
        self.drill_filter: tuple[str, str] | None = None
        # Cache current dataframe for lookups
        self.current_df = pd.DataFrame()

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(classes="top-bar"):
            with Horizontal(classes="controls"):
                yield Label("Query: ")
                yield Input(placeholder="e.g. larger:5M", id="query_input")
                yield Button("Scan", id="scan_btn", variant="primary")
                yield Button("Stop", id="stop_btn", variant="error", disabled=True)

            with Horizontal(classes="controls"):
                yield Label("View: ")
                yield Select.from_values(
                    ["Top Senders", "Usage by Month", "All Messages"],
                    value="Top Senders",
                    id="view_select",
                )
                yield Static("", id="stats_display")

            yield ProgressBar(total=100, show_eta=False, id="scan_progress")

        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_data()
        self.set_interval(0.5, self.update_progress_ui)

    async def update_progress_ui(self) -> None:
        """Update progress bar and stats."""
        total, completed = await self.storage.get_total_counts()

        bar = self.query_one(ProgressBar)
        if total > 0:
            bar.total = total
            bar.progress = completed

        # Only calc stats occasionally or if changed?
        if self.query_one("#scan_btn", Button).disabled:
            self.query_one("#stats_display", Static).update(
                f"Scanning: {completed}/{total}"
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan_btn":
            query = self.query_one("#query_input", Input).value
            self.start_scan(query)
        elif event.button.id == "stop_btn":
            self.stop_scan()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.control.id == "view_select":
            self.current_view = str(event.value)
            self.drill_filter = None  # Reset drill down when view changes
            asyncio.create_task(self.refresh_data())

    def start_scan(self, query: str) -> None:
        self.query_one("#scan_btn").disabled = True
        self.query_one("#stop_btn").disabled = False
        self.query_one("#scan_progress").add_class("progress-visible")
        self.query_one(ProgressBar).update(progress=0)

        self.worker = self.run_worker(
            self.scan_task(query), exclusive=True, thread=False
        )

    def stop_scan(self) -> None:
        if self.worker:
            self.worker.cancel()

    async def scan_task(self, query: str) -> None:
        self.scanner = AsyncGmailScanner(self.creds, self.storage)
        try:
            await self.scanner.fetch_list(query=query)
            while True:
                if self.worker and self.worker.is_cancelled:
                    break
                processed = await self.scanner.fetch_details()
                if processed == 0:
                    break
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
        finally:
            await self.scanner.close()
            self.query_one("#scan_btn").disabled = False
            self.query_one("#stop_btn").disabled = True
            self.query_one("#scan_progress").remove_class("progress-visible")
            await self.refresh_data()

    async def action_refresh_data(self) -> None:
        await self.refresh_data()

    async def action_go_back(self) -> None:
        if self.drill_filter:
            self.drill_filter = None
            await self.refresh_data()

    async def action_mark_selected(self) -> None:
        """Mark selected messages with a label."""
        table = self.query_one(DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            row_data = table.get_row(row_key)
        except Exception:
            self.notify("No row selected.", severity="warning")
            return

        ids_to_mark: list[str] = []
        label_desc = ""

        # Determine what to mark based on view
        if self.drill_filter:
            # We are viewing specific messages.
            # In drill-down view, we need to know the ID.
            # Currently drill-down columns: Date, Subject, Size. ID is not shown but we can stash it?
            # Or we can look it up in self.current_df.
            # But the table row doesn't have the ID.
            # Let's fix refresh_data to store IDs in row keys or be able to look them up.

            # Since we didn't use row keys explicitly, Textual generated them.
            # We need to rebuild the table with explicit keys equal to message ID for messages
            pass

        # We need a robust way to get IDs.
        # Strategy: Run a query on self.current_df based on the selection.

        df = self.current_df
        if df.empty:
            self.notify("No data available.", severity="error")
            return

        if self.drill_filter:
            # Drill down view: Individual messages
            # Problem: We need to know which message this row corresponds to.
            # We can use the row index if we sorted the DF exactly the same way.
            # Better: Update refresh_data to use Message ID as row key for message lists.

            # If we are in drill-down, the row key SHOULD be the message ID (see refresh_data update below)
            # Wait, refresh_data below doesn't set row key yet. I will update it.

            mid = row_key.value  # If we set key=mid
            ids_to_mark = [str(mid)] if mid else []
            label_desc = "1 message"

        elif self.current_view == "Top Senders":
            sender = row_data[0]  # Sender email
            ids_to_mark = df[df["sender"] == sender]["id"].tolist()
            label_desc = f"all messages from {sender}"

        elif self.current_view == "Usage by Month":
            month = row_data[0]  # YYYY-MM
            ids_to_mark = df[df["year_month"] == month]["id"].tolist()
            label_desc = f"all messages in {month}"

        elif self.current_view == "All Messages":
            # We need ID as key here too
            mid = row_key.value
            ids_to_mark = [str(mid)] if mid else []
            label_desc = "1 message"

        if not ids_to_mark:
            self.notify("No messages found to mark.", severity="warning")
            return

        self.notify(f"Marking {len(ids_to_mark)} messages... ({label_desc})")

        # Run in worker
        self.run_worker(self.mark_task(ids_to_mark), exclusive=False, thread=False)

    async def mark_task(self, ids: list[str]) -> None:
        scanner = AsyncGmailScanner(self.creds, self.storage)
        try:
            count = await scanner.add_labels(ids)
            self.notify(
                f"Successfully marked {count} messages.", severity="information"
            )
        except Exception as e:
            self.notify(f"Error marking messages: {e}", severity="error")
        finally:
            await scanner.close()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Handle drill down
        if self.current_view == "Top Senders" and not self.drill_filter:
            row = self.query_one(DataTable).get_row(event.row_key)
            sender = row[0]
            self.drill_filter = ("sender", str(sender))
            asyncio.create_task(self.refresh_data())

        elif self.current_view == "Usage by Month" and not self.drill_filter:
            row = self.query_one(DataTable).get_row(event.row_key)
            month = row[0]
            self.drill_filter = ("month", str(month))
            asyncio.create_task(self.refresh_data())

    async def refresh_data(self) -> None:
        """Reload data from DB and update table."""
        rows = await self.storage.get_all_completed_messages()
        analyzer = GmailAnalyzer(rows)
        self.current_df = analyzer.df
        df = self.current_df

        table = self.query_one(DataTable)
        table.clear(columns=True)

        # Apply Drill Filter
        display_df = df

        if self.drill_filter:
            ftype, fval = self.drill_filter
            if ftype == "sender":
                display_df = df[df["sender"] == fval]
                title = f"Messages from {fval}"
            elif ftype == "month":
                display_df = df[df["year_month"] == fval]
                title = f"Messages in {fval}"
            else:
                title = "Messages"

            self.query_one("#stats_display", Static).update(
                f"{title} ({len(display_df)} msgs)"
            )
            table.add_columns("Date", "Subject", "Size (MB)")

            sorted_df = display_df.sort_values("size", ascending=False).head(500)
            for _, row in sorted_df.iterrows():
                # Use Message ID as Row Key for easy retrieval
                table.add_row(
                    str(row["date"]),
                    str(row["subject"])[:50],
                    f"{row['size'] / (1024 * 1024):.2f}",
                    key=str(row["id"]),
                )
            return

        # Normal Views
        if self.current_view == "Top Senders":
            table.add_columns("Sender", "Size (MB)", "Msg Count")
            if not df.empty:
                grouped = (
                    df.groupby("sender")
                    .agg({"size": "sum", "id": "count"})
                    .sort_values("size", ascending=False)
                    .head(100)
                )
                for sender, row in grouped.iterrows():
                    table.add_row(
                        str(sender),
                        f"{row['size'] / (1024 * 1024):.2f}",
                        str(row["id"]),
                        key=str(sender),  # Use sender as key
                    )

        elif self.current_view == "Usage by Month":
            table.add_columns("Month", "Size (MB)", "Msg Count")
            if not df.empty:
                grouped = (
                    df.groupby("year_month")
                    .agg({"size": "sum", "id": "count"})
                    .sort_index(ascending=False)
                )
                for month, row in grouped.iterrows():
                    table.add_row(
                        str(month),
                        f"{row['size'] / (1024 * 1024):.2f}",
                        str(row["id"]),
                        key=str(month),  # Use month as key
                    )

        elif self.current_view == "All Messages":
            table.add_columns("Date", "Sender", "Subject", "Size (MB)")
            if not df.empty:
                sorted_df = df.sort_values("size", ascending=False).head(500)
                for _, row in sorted_df.iterrows():
                    table.add_row(
                        str(row["date"]),
                        str(row["sender"]),
                        str(row["subject"])[:40],
                        f"{row['size'] / (1024 * 1024):.2f}",
                        key=str(row["id"]),  # Use ID as key
                    )

        # Update Stats
        count, size = analyzer.summary()
        self.query_one("#stats_display", Static).update(
            f"Total: {count} msgs | {size / (1024 * 1024):.2f} MB"
        )
