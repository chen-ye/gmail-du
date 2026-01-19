import argparse
import asyncio

from rich.console import Console
from rich.table import Table

from analyzer import GmailAnalyzer
from auth import authenticate
from scanner import AsyncGmailScanner
from storage import Storage

console = Console()


def print_summary(count, total_size):
    table = Table(title="Overall Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Total Messages Analyzed", str(count))
    table.add_row("Total Size", f"{total_size / (1024 * 1024):.2f} MB")
    console.print(table)


def print_grouped_data(title, data, value_col="Size (MB)"):
    table = Table(title=title)
    table.add_column("Group", style="green")
    table.add_column(value_col, justify="right", style="yellow")

    for label, size in data.items():
        mb_size = size / (1024 * 1024)
        table.add_row(str(label), f"{mb_size:.2f}")

    console.print(table)


async def async_main():
    parser = argparse.ArgumentParser(
        description="Gmail Disk Usage Analyzer (Async/Resumable)"
    )
    parser.add_argument(
        "--query", "-q", type=str, default="", help="Gmail search query"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit messages to scan (default: Unlimited)",
    )
    parser.add_argument("--by-sender", action="store_true", help="Group by sender")
    parser.add_argument("--by-month", action="store_true", help="Group by month")
    parser.add_argument(
        "--reset", action="store_true", help="Clear local cache/db before starting"
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch interactive TUI (Text User Interface)",
    )

    args = parser.parse_args()

    # 1. Init DB
    storage = Storage()
    if args.reset:
        import os

        if os.path.exists("gmail_du.db"):
            os.remove("gmail_du.db")
            console.print("[yellow]Database cleared.[/yellow]")

    await storage.init_db()

    # 2. Auth
    try:
        creds = authenticate()
    except Exception as e:
        console.print(f"[bold red]Authentication failed:[/bold red] {e}")
        return

    # TUI Mode
    if args.tui:
        from tui import GmailDUApp

        app = GmailDUApp(storage, creds)
        await app.run_async()
        return

    # CLI Mode
    console.print("[bold blue]Gmail DU[/bold blue] (CLI Mode)")

    scanner = AsyncGmailScanner(creds, storage)

    try:
        total, completed = await storage.get_total_counts()
        console.print(
            f"Database status: {total} messages found, {completed} details fetched."
        )

        if args.limit and total >= args.limit:
            console.print("Limit reached in DB. Skipping list fetch.")
        else:
            await scanner.fetch_list(query=args.query, limit=args.limit)

        while True:
            processed = await scanner.fetch_details()
            if processed == 0:
                break
            console.print(f"Processed batch of {processed}. Checking for more...")

    finally:
        await scanner.close()

    console.print("Loading data for analysis...")
    rows = await storage.get_all_completed_messages()
    analyzer = GmailAnalyzer(rows)

    count, total_size = analyzer.summary()
    print_summary(count, total_size)

    if args.by_sender:
        sender_data = analyzer.group_by_sender()
        print_grouped_data("Top Senders by Size", sender_data)

    if args.by_month:
        month_data = analyzer.group_by_month()
        print_grouped_data("Usage by Month", month_data)


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user. State saved.[/red]")


if __name__ == "__main__":
    main()
