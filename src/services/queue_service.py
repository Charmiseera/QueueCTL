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

def retry_dlq_job(job_id):
    """Re-enqueues a dead job from the DLQ, resetting attempts to 0."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, state FROM jobs WHERE id = ?;", (job_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Job {job_id} not found.")
        if row["state"] != "dead":
            raise ValueError(f"Job {job_id} is not in dead state (current state: {row['state']}).")

        now_str = datetime.utcnow().isoformat() + "Z"
        conn.execute("""
        UPDATE jobs
        SET state = 'pending', attempts = 0, run_at = ?, updated_at = ?, worker_id = NULL
        WHERE id = ?;
        """, (now_str, now_str, job_id))
        conn.commit()

def recover_orphaned_jobs():
    """Finds jobs processing by workers who haven't heartbeat in 15 seconds, and resets them to pending."""
    init_db()
    now = datetime.utcnow()
    dead_worker_ids = []
    
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, last_heartbeat FROM workers;")
        for row in cursor.fetchall():
            hb_str = row["last_heartbeat"].replace("Z", "")
            try:
                # Support parsing timestamps with or without fractional seconds
                if "." in hb_str:
                    hb_dt = datetime.strptime(hb_str, "%Y-%m-%dT%H:%M:%S.%f")
                else:
                    hb_dt = datetime.strptime(hb_str, "%Y-%m-%dT%H:%M:%S")
                    
                if (now - hb_dt).total_seconds() > 15.0:
                    dead_worker_ids.append(row["id"])
            except Exception as e:
                # If parsing fails, treat worker as dead
                dead_worker_ids.append(row["id"])

        if not dead_worker_ids:
            return

        now_str = now.isoformat() + "Z"
        # Reset jobs processing on these dead workers
        for worker_id in dead_worker_ids:
            # Check how many jobs will be affected
            cursor_jobs = conn.execute("SELECT id FROM jobs WHERE worker_id = ? AND state = 'processing';", (worker_id,))
            jobs_to_recover = [r["id"] for r in cursor_jobs.fetchall()]
            
            for job_id in jobs_to_recover:
                # Reset to pending so it runs again
                conn.execute("""
                UPDATE jobs
                SET state = 'pending', worker_id = NULL, run_at = ?, updated_at = ?
                WHERE id = ?;
                """, (now_str, now_str, job_id))
            
            # Remove the dead worker
            conn.execute("DELETE FROM workers WHERE id = ?;", (worker_id,))
            
        conn.commit()


