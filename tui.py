from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, Input, Button, DataTable, Label, ProgressBar, Select, Static
from textual.screen import Screen
from textual.binding import Binding

import asyncio
import pandas as pd
from scanner import AsyncGmailScanner
from storage import Storage
from analyzer import GmailAnalyzer
from auth import authenticate

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
    ]

    def __init__(self, storage, creds):
        super().__init__()
        self.storage = storage
        self.creds = creds
        self.scanner = None
        self.worker = None
        self.current_view = "Top Senders"
        self.drill_filter = None # tuple (type, value) e.g. ('sender', 'foo@bar.com')

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
                    id="view_select"
                )
                yield Static("", id="stats_display")

            yield ProgressBar(total=100, show_eta=False, id="scan_progress")

        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_data()
        self.set_interval(0.5, self.update_progress_ui)

    async def update_progress_ui(self):
        """Update progress bar and stats."""
        total, completed = await self.storage.get_total_counts()
        
        bar = self.query_one(ProgressBar)
        if total > 0:
            bar.total = total
            bar.progress = completed
        
        # Only calc stats occasionally or if changed? 
        # For now, lightweight enough to do check
        # But analyzer needs to load all rows... heavy.
        # Let's only update the stats text if we are scanning
        if self.query_one("#scan_btn").disabled:
            self.query_one("#stats_display").update(f"Scanning: {completed}/{total}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan_btn":
            query = self.query_one("#query_input").value
            self.start_scan(query)
        elif event.button.id == "stop_btn":
            self.stop_scan()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.control.id == "view_select":
            self.current_view = event.value
            self.drill_filter = None # Reset drill down when view changes
            asyncio.create_task(self.refresh_data())

    def start_scan(self, query: str):
        self.query_one("#scan_btn").disabled = True
        self.query_one("#stop_btn").disabled = False
        self.query_one("#scan_progress").add_class("progress-visible")
        self.query_one(ProgressBar).update(progress=0)
        
        self.worker = self.run_worker(
            self.scan_task(query), 
            exclusive=True, 
            thread=False
        )

    def stop_scan(self):
        if self.worker:
            self.worker.cancel()

    async def scan_task(self, query: str):
        self.scanner = AsyncGmailScanner(self.creds, self.storage)
        try:
            await self.scanner.fetch_list(query=query)
            while True:
                if self.worker.is_cancelled: break
                processed = await self.scanner.fetch_details()
                if processed == 0: break
                # allow UI updates
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

    async def action_refresh_data(self):
        await self.refresh_data()

    async def action_go_back(self):
        if self.drill_filter:
            self.drill_filter = None
            # Reset select to what it was? 
            # If we were in "Top Senders" and drilled down, we want to go back to "Top Senders"
            # The view_select likely didn't change, just the table content.
            await self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        # Handle drill down
        if self.current_view == "Top Senders" and not self.drill_filter:
            # Row key or cell? 
            # We put sender email in the first column.
            row = self.query_one(DataTable).get_row(event.row_key)
            sender = row[0]
            self.drill_filter = ('sender', sender)
            asyncio.create_task(self.refresh_data())
            
        elif self.current_view == "Usage by Month" and not self.drill_filter:
            row = self.query_one(DataTable).get_row(event.row_key)
            month = row[0]
            self.drill_filter = ('month', month)
            asyncio.create_task(self.refresh_data())

    async def refresh_data(self):
        """Reload data from DB and update table."""
        # This is heavy for large DBs. Ideally we cache the DF.
        rows = await self.storage.get_all_completed_messages()
        analyzer = GmailAnalyzer(rows)
        
        table = self.query_one(DataTable)
        table.clear(columns=True)
        
        # Apply Drill Filter
        df = analyzer.df
        display_df = df
        
        if self.drill_filter:
            ftype, fval = self.drill_filter
            if ftype == 'sender':
                display_df = df[df['sender'] == fval]
                title = f"Messages from {fval}"
            elif ftype == 'month':
                display_df = df[df['year_month'] == fval]
                title = f"Messages in {fval}"
            
            # Show file list mode
            self.query_one("#stats_display").update(f"{title} ({len(display_df)} msgs)")
            table.add_columns("Date", "Subject", "Size (MB)")
            
            sorted_df = display_df.sort_values('size', ascending=False).head(500)
            for _, row in sorted_df.iterrows():
                table.add_row(
                    str(row['date']),
                    str(row['subject'])[:50], 
                    f"{row['size'] / (1024*1024):.2f}"
                )
            return

        # Normal Views
        if self.current_view == "Top Senders":
            table.add_columns("Sender", "Size (MB)", "Msg Count")
            if not df.empty:
                grouped = df.groupby('sender').agg({'size': 'sum', 'id': 'count'}).sort_values('size', ascending=False).head(100)
                for sender, row in grouped.iterrows():
                    table.add_row(
                        str(sender), 
                        f"{row['size'] / (1024*1024):.2f}",
                        str(row['id'])
                    )
        
        elif self.current_view == "Usage by Month":
            table.add_columns("Month", "Size (MB)", "Msg Count")
            if not df.empty:
                grouped = df.groupby('year_month').agg({'size': 'sum', 'id': 'count'}).sort_index(ascending=False)
                for month, row in grouped.iterrows():
                    table.add_row(
                        str(month),
                        f"{row['size'] / (1024*1024):.2f}",
                        str(row['id'])
                    )

        elif self.current_view == "All Messages":
            table.add_columns("Date", "Sender", "Subject", "Size (MB)")
            if not df.empty:
                sorted_df = df.sort_values('size', ascending=False).head(500)
                for _, row in sorted_df.iterrows():
                    table.add_row(
                        str(row['date']),
                        str(row['sender']),
                        str(row['subject'])[:40],
                        f"{row['size'] / (1024*1024):.2f}"
                    )
        
        # Update Stats
        count, size = analyzer.summary()
        self.query_one("#stats_display").update(f"Total: {count} msgs | {size / (1024*1024):.2f} MB")
