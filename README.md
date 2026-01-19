# Gmail Disk Usage Analyzer (gmail-du)

A Python CLI tool to visualize Gmail storage usage, grouped by various factors like sender and date.

## Features

*   **Asynchronous Scanning**: Uses `aiohttp` for high-performance concurrent fetching of message metadata, capable of processing thousands of messages quickly.
*   **Resumable**: Stores progress in a local SQLite database (`gmail_du.db`). You can stop (Ctrl+C) and restart the scan at any time without losing progress.
*   **Smart Analysis**: Aggregates storage usage stats by **Sender** and **Month**.
*   **OAuth2 Secure**: Runs locally on your machine using standard Google OAuth2 authentication.

## Architecture

*   **Scanner**: Fetches message lists and details using the Gmail API. It separates the "listing" phase (finding IDs) from the "fetching" phase (getting details).
*   **Storage**: Uses `aiosqlite` to persist state.
    *   `messages` table: Stores message IDs, sizes, headers, and fetch status.
    *   `state` table: Tracks pagination tokens (e.g., `nextPageToken`) to resume listings.
*   **Analyzer**: Loads completed records from the DB into `pandas` for grouping and aggregation.

## Setup

1.  **Install uv**:
    ```bash
    pip install uv
    ```

2.  **Install Dependencies**:
    Sync the project environment:
    ```bash
    uv sync
    ```

3.  **Get Credentials**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project.
    *   Enable the **Gmail API**.
    *   Create **OAuth 2.0 Client IDs** (Desktop App).
    *   Download the JSON file and rename it to `credentials.json`.
    *   Place `credentials.json` in this directory.

## Usage

Run the tool using `uv run`:

```bash
uv run main.py [options]
```

### Options

*   `-q, --query`: Gmail search query (e.g., `'larger:5M'`, `'category:promotions'`, `'older_than:1y'`).
*   `-l, --limit`: Limit the total number of messages to scan (default: **Unlimited**).
*   `--by-sender`: Show storage usage grouped by sender.
*   `--by-month`: Show storage usage grouped by month.
*   `--reset`: Clear the local database (`gmail_du.db`) and cache before starting a fresh scan.

### Examples

**Scan top 1000 messages:**
```bash
uv run main.py -l 1000
```

**Resume a previous scan:**
Just run the command again. It will automatically pick up where it left off.
```bash
uv run main.py
```

**Analyze usage by sender for huge emails:**
```bash
uv run main.py -q "larger:10M" --by-sender
```

**Force a fresh start:**
```bash
uv run main.py --reset
```
