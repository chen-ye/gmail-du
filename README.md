# Gmail Disk Usage Analyzer (gmail-du)

A Python CLI tool to visualize Gmail storage usage, grouped by various factors like sender and date. Now featuring an interactive TUI!

## Features

*   **Interactive TUI**: A terminal user interface (`--tui`) akin to `ncdu` for browsing storage usage.
*   **Mark Messages**: Interactively mark messages or groups of messages in the TUI (Key: `m`). Marked messages get the label `gmail-du-marked` in Gmail, making them easy to find and delete.
*   **Asynchronous Scanning**: Uses `aiohttp` for high-performance concurrent fetching.
*   **Resumable**: Stores progress in a local SQLite database (`gmail_du.db`).
*   **Analysis**: Aggregates stats by Sender and Month.

## Setup

1.  **Install uv**:
    ```bash
    pip install uv
    ```

2.  **Install Dependencies**:
    ```bash
    uv sync
    ```

3.  **Get Credentials**:
    *   Create **OAuth 2.0 Client IDs** (Desktop App) in Google Cloud Console.
    *   Save as `credentials.json` in this directory.

## Usage

### Interactive Mode (TUI)

The recommended way to explore your inbox:

```bash
uv run main.py --tui
```

*   **Scan**: Enter a query (e.g. `larger:1M`) and click Scan.
*   **Navigate**: Use arrow keys to select a Sender or Month.
*   **Drill Down**: Press **Enter** on a Sender to see their specific messages.
*   **Mark Messages**: Press **m** to apply the label `gmail-du-marked` to the selected message or group (e.g., all emails from that sender).
*   **Back**: Press **Escape** to go back to the main view.

### CLI Mode

Standard command line operation:

```bash
uv run main.py [options]
```

**Options**:
*   `-q, --query`: Gmail search query.
*   `-l, --limit`: Limit messages to scan.
*   `--by-sender`, `--by-month`: Grouping flags.
*   `--reset`: Clear database.

**Examples**:
```bash
# Interactive mode
uv run main.py --tui

# Scan top 1000 messages via CLI
uv run main.py -l 1000 --by-sender
```
