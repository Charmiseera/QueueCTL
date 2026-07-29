import subprocess
import time
import uuid
import os
import sys
from datetime import datetime
from src.services.db_service import get_connection, init_db
from src.models.job import Job
from src.models.worker import Worker

# Global flag to signal workers to stop gracefully (e.g. from Ctrl+C signal handler)
stop_requested = False

def claim_job_simple(worker_id):
    """Simple claim query for T010. We will upgrade this to atomic BEGIN IMMEDIATE in US3."""
    now_str = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        # Find first eligible job
        cursor = conn.execute("""
        SELECT * FROM jobs
        WHERE (state = 'pending' OR state = 'failed') AND datetime(run_at) <= datetime(?)
        ORDER BY created_at ASC
        LIMIT 1;
        """, (now_str,))
        row = cursor.fetchone()
        if not row:
            return None
        
        job = Job.from_row(row)
        
        # Claim it
        conn.execute("""
        UPDATE jobs
        SET state = 'processing', worker_id = ?, updated_at = ?, attempts = attempts + 1
        WHERE id = ?;
        """, (worker_id, now_str, job.id))
        conn.commit()
        
        job.state = 'processing'
        job.worker_id = worker_id
        job.attempts += 1
        job.updated_at = now_str
        return job

def run_job(job):
    """Executes a job's command via shell and returns the exit code."""
    try:
        # Run command using system shell
        process = subprocess.Popen(
            job.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for the process to complete
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr
    except Exception as e:
        return -1, "", str(e)

def update_job_status(job_id, success, attempts, max_retries, backoff_base=2.0):
    """Updates job state to completed, failed, or dead based on success and attempts."""
    now_str = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        if success:
            conn.execute("""
            UPDATE jobs
            SET state = 'completed', worker_id = NULL, updated_at = ?
            WHERE id = ?;
            """, (now_str, job_id))
        else:
            if attempts >= max_retries:
                # Move to DLQ (dead)
                conn.execute("""
                UPDATE jobs
                SET state = 'dead', worker_id = NULL, updated_at = ?
                WHERE id = ?;
                """, (now_str, job_id))
            else:
                # Calculate backoff delay
                delay = float(backoff_base) ** attempts
                # Scheduled execution time
                run_at_dt = datetime.utcnow().timestamp() + delay
                run_at_str = datetime.utcfromtimestamp(run_at_dt).isoformat() + "Z"
                
                conn.execute("""
                UPDATE jobs
                SET state = 'failed', worker_id = NULL, run_at = ?, updated_at = ?
                WHERE id = ?;
                """, (run_at_str, now_str, job_id))
        conn.commit()

def register_worker(worker_id):
    """Registers worker process in DB."""
    init_db()
    pid = os.getpid()
    now_str = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO workers (id, pid, last_heartbeat, should_stop)
        VALUES (?, ?, ?, 0);
        """, (worker_id, pid, now_str))
        conn.commit()

def heartbeat_worker(worker_id):
    """Updates heartbeat for worker process."""
    now_str = datetime.utcnow().isoformat() + "Z"
    with get_connection() as conn:
        conn.execute("""
        UPDATE workers
        SET last_heartbeat = ?
        WHERE id = ?;
        """, (now_str, worker_id))
        conn.commit()

def check_remote_stop(worker_id):
    """Checks if worker has been signaled to stop from database."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT should_stop FROM workers WHERE id = ?;", (worker_id,))
        row = cursor.fetchone()
        return (row and row["should_stop"] == 1)

def clean_worker_db(worker_id):
    """Deregisters worker from DB upon graceful stop."""
    with get_connection() as conn:
        conn.execute("DELETE FROM workers WHERE id = ?;", (worker_id,))
        conn.commit()

def worker_loop(worker_id=None):
    """Main worker loop starting in the foreground."""
    global stop_requested
    
    if not worker_id:
        worker_id = str(uuid.uuid4())
        
    register_worker(worker_id)
    print(f"Worker {worker_id} started (PID: {os.getpid()})...")
    
    # Load backoff configuration base
    backoff_base = 2.0
    with get_connection() as conn:
        cursor = conn.execute("SELECT value FROM config WHERE key = 'backoff-base'")
        row = cursor.fetchone()
        if row:
            backoff_base = float(row["value"])

    try:
        while not stop_requested:
            # Update heartbeat
            heartbeat_worker(worker_id)
            
            # Check remote stop signal
            if check_remote_stop(worker_id):
                print(f"Worker {worker_id} stopping due to remote stop signal.")
                break
                
            # Attempt to claim a job (simple claim for now)
            job = claim_job_simple(worker_id)
            if job:
                print(f"[{worker_id}] Processing Job {job.id}: '{job.command}' (Attempt {job.attempts}/{job.max_retries})")
                
                # Execute the subprocess
                returncode, stdout, stderr = run_job(job)
                
                # Update status
                success = (returncode == 0)
                update_job_status(job.id, success, job.attempts, job.max_retries, backoff_base)
                
                if success:
                    print(f"[{worker_id}] Job {job.id} completed successfully.")
                else:
                    print(f"[{worker_id}] Job {job.id} failed (exit code: {returncode}).")
                
                # Update heartbeat immediately after job completes
                heartbeat_worker(worker_id)
            else:
                # Sleep if no jobs
                time.sleep(1)
    finally:
        print(f"Worker {worker_id} shutting down cleanly...")
        clean_worker_db(worker_id)
