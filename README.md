# Gmail Disk Usage Analyzer (gmail-du)

A Python CLI tool to visualize Gmail storage usage, grouped by various factors like sender and date.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt --break-system-packages
    ```
    *(Note: The `--break-system-packages` flag might be required in some managed environments where virtual environments are not easily created without root access. Ideally, use a virtual environment if possible.)*

2.  **Get Credentials**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project.
    *   Enable the **Gmail API**.
    *   Create **OAuth 2.0 Client IDs** (Desktop App).
    *   Download the JSON file and rename it to `credentials.json`.
    *   Place `credentials.json` in this directory.

## Usage

Run the tool using Python:

```bash
python3 main.py [options]
```

### Options

*   `-q, --query`: Gmail search query (e.g., `'larger:5M'`, `'category:promotions'`).
*   `-l, --limit`: Limit the number of messages to scan (default: 100).
*   `--by-sender`: specific flag to show usage grouped by sender.
*   `--by-month`: specific flag to show usage grouped by month.

### Examples

**Scan top 100 messages:**
```bash
python3 main.py
```

**Scan messages larger than 1MB and group by sender:**
```bash
python3 main.py -q "larger:1M" -l 500 --by-sender
```

**Analyze usage over time:**
```bash
python3 main.py -l 1000 --by-month
```
