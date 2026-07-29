import os

# Database Path (persisted in the root of the project)
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "queuectl.db"))

# Default Settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0
