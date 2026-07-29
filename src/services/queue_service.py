import json
from datetime import datetime
from src.services.db_service import get_connection, init_db
from src.models.job import Job

def enqueue_job(job_id, command, max_retries=None):
    """Enqueues a new job in the database. Installs schema first if necessary."""
    init_db()
    with get_connection() as conn:
        # Determine max_retries from config if not specified
        if max_retries is None:
            cursor = conn.execute("SELECT value FROM config WHERE key = 'max-retries'")
            row = cursor.fetchone()
            max_retries = int(row["value"]) if row else 3

        now_str = datetime.utcnow().isoformat() + "Z"
        
        conn.execute("""
        INSERT INTO jobs (id, command, state, attempts, max_retries, worker_id, run_at, created_at, updated_at)
        VALUES (?, ?, 'pending', 0, ?, NULL, ?, ?, ?);
        """, (job_id, command, max_retries, now_str, now_str, now_str))
        conn.commit()

def list_jobs(state=None):
    """Retrieves list of jobs, optionally filtered by state."""
    init_db()
    with get_connection() as conn:
        if state:
            cursor = conn.execute("""
            SELECT id, command, state, attempts, max_retries, worker_id, run_at, created_at, updated_at
            FROM jobs
            WHERE state = ?
            ORDER BY created_at ASC;
            """, (state,))
        else:
            cursor = conn.execute("""
            SELECT id, command, state, attempts, max_retries, worker_id, run_at, created_at, updated_at
            FROM jobs
            ORDER BY created_at ASC;
            """)
        
        return [Job.from_row(row) for row in cursor.fetchall()]
