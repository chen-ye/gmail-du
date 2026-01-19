import argparse
from auth import authenticate
from scanner import GmailScanner
from analyzer import GmailAnalyzer
from googleapiclient.discovery import build
from rich.console import Console
from rich.table import Table

console = Console()

def print_summary(count, total_size):
    table = Table(title="Overall Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Total Messages", str(count))
    table.add_row("Total Size", f"{total_size / (1024*1024):.2f} MB")
    console.print(table)

def print_grouped_data(title, data, value_col="Size (MB)"):
    table = Table(title=title)
    table.add_column("Group", style="green")
    table.add_column(value_col, justify="right", style="yellow")
    
    for label, size in data.items():
        mb_size = size / (1024*1024)
        table.add_row(str(label), f"{mb_size:.2f}")
    
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="Gmail Disk Usage Analyzer")
    parser.add_argument('--query', '-q', type=str, default='', help="Gmail search query")
    parser.add_argument('--limit', '-l', type=int, default=100, help="Limit messages to scan")
    parser.add_argument('--by-sender', action='store_true', help="Group by sender")
    parser.add_argument('--by-month', action='store_true', help="Group by month")
    
    args = parser.parse_args()

    console.print("[bold blue]Gmail DU[/bold blue]")

    try:
        creds = authenticate()
        service = build('gmail', 'v1', credentials=creds)
    except Exception as e:
        console.print(f"[bold red]Authentication failed:[/bold red] {e}")
        return

    scanner = GmailScanner(service)
    
    console.print(f"Scanning messages (Query: '{args.query}', Limit: {args.limit})...")
    messages = scanner.list_messages(query=args.query, limit=args.limit)
    
    if not messages:
        console.print("No messages found.")
        return

    console.print(f"Found {len(messages)} messages. Fetching details...")
    details = scanner.get_message_details([m['id'] for m in messages])
    
    analyzer = GmailAnalyzer(details)
    count, total_size = analyzer.summary()
    
    print_summary(count, total_size)
    
    if args.by_sender:
        sender_data = analyzer.group_by_sender()
        print_grouped_data("Top Senders by Size", sender_data)
        
    if args.by_month:
        month_data = analyzer.group_by_month()
        print_grouped_data("Usage by Month", month_data)

if __name__ == '__main__':
    main()
