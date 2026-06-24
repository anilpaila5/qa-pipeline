"""
Configuration for BrowserStack bulk test case creation.
Folder IDs and CSV file mappings are defined here.
Credentials are NEVER stored here — they are prompted at runtime.
"""

BROWSERSTACK_API_BASE = "https://test-management.browserstack.com/api/v1"

# Map each CSV filename to its target BrowserStack folder ID.
# To add a new batch: add another entry with the CSV filename and folder ID.
FOLDER_MAPPINGS = {
    "CreateObjectModalTestCases.csv": {
        "folder_id": 49769713,
        "description": "Create Object Modal test cases (C_RENT23561)",
    },
    "AdaptiveObjectsGridTestCases.csv": {
        "folder_id": 49769742,
        "description": "Adaptive Objects Grid test cases (C_RENT23562)",
    },
    "CreateGroupTestCases.csv": {
        "folder_id": 49769772,
        "description": "Create Group test cases (C_RENT23560)",
    },
}

# Directory (relative to this file) where CSV input files live.
INPUT_DIR = "input"

# HTTP request timeout in seconds.
REQUEST_TIMEOUT = 30

# Delay (seconds) between API calls to avoid rate-limiting.
RATE_LIMIT_DELAY = 0.3

# ── Retry / back-off configuration ──────────────────────────────────────────

# Maximum number of total attempts (1 original + N-1 retries).
RETRY_MAX_ATTEMPTS = 4

# Initial wait before the first retry (seconds). Doubles each attempt.
RETRY_WAIT_INITIAL = 1.0

# Upper bound on any single wait interval (seconds).
RETRY_WAIT_MAX = 60.0

# HTTP status codes that are transient and worth retrying.
# 400 / 401 / 403 / 404 are NOT here — those won't fix themselves.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# ── Concurrency ──────────────────────────────────────────────────────────────

# Default number of parallel worker threads.
# 1 = fully sequential (original behaviour).
# Override with --concurrency N on the CLI.
# Recommended range: 3–5. Higher values may trigger BrowserStack rate limits.
DEFAULT_CONCURRENCY = 1
