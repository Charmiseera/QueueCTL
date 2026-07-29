import sqlite3
import os
from src.config import DB_PATH, DEFAULT_MAX_RETRIES, DEFAULT_BACKOFF_BASE

def get_connection():
    """Acquires a database connection and configures it."""
    # Ensure parent directory of database exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0) # Enable timeout for concurrency lock queueing
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # Enable WAL mode for better concurrency performance
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Creates the schema if it does not exist and installs default configurations."""
    with get_connection() as conn:
        # Create jobs table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            max_retries INTEGER NOT NULL,
            worker_id TEXT,
            run_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE SET NULL
        );
        """)

        # Create workers table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            pid INTEGER NOT NULL,
            last_heartbeat TEXT NOT NULL,
            should_stop INTEGER DEFAULT 0
        );
        """)

        # Create config table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # Install default configurations if not present
        conn.execute("""
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('max-retries', ?);
        """, (str(DEFAULT_MAX_RETRIES),))

        conn.execute("""
        INSERT OR IGNORE INTO config (key, value)
        VALUES ('backoff-base', ?);
        """, (str(DEFAULT_BACKOFF_BASE),))
        
        conn.commit()
