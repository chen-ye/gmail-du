# Gmail Disk Usage Analyzer (gmail-du)

A Python CLI tool to visualize Gmail storage usage, grouped by various factors like sender and date.

## Features

*   **Asynchronous Scanning**: Uses `aiohttp` for high-performance concurrent fetching of message metadata.
*   **Resumable**: Stores progress in a local SQLite database (`gmail_du.db`). You can stop and restart the scan at any time without losing progress.
*   **Analysis**: aggregated stats by Sender and Month.

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

*   `-q, --query`: Gmail search query (e.g., `'larger:5M'`, `'category:promotions'`).
*   `-l, --limit`: Limit the number of messages to scan.
*   `--by-sender`: Show usage grouped by sender.
*   `--by-month`: Show usage grouped by month.
*   `--reset`: Clear the local database and cache before starting.

### Examples

**Scan top 1000 messages:**
```bash
uv run main.py -l 1000
```

**Resume a previous scan:**
Just run the command again. It will automatically pick up where it left off.

**Analyze usage by sender:**
```bash
uv run main.py --by-sender
```

**Force a fresh start:**
```bash
uv run main.py --reset
```
