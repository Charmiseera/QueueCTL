import subprocess
import time
import uuid
import os
import sys
import threading
from datetime import datetime
from src.services.db_service import get_connection, init_db, claim_job_atomic
from src.models.job import Job
from src.models.worker import Worker
from src.services.queue_service import recover_orphaned_jobs

# Global flag to signal workers to stop gracefully (e.g. from Ctrl+C signal handler)
stop_requested = False

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

def heartbeat_daemon(worker_id, stop_event):
    """Periodically heartbeats to DB in a separate thread to prevent timeouts during long command execution."""
    while not stop_event.is_set():
        try:
            heartbeat_worker(worker_id)
        except Exception:
            pass
        # Wait 5 seconds, checking stop_event in small intervals
        for _ in range(50):
            if stop_event.is_set():
                break
            time.sleep(0.1)

def worker_loop(worker_id=None):
    """Main worker loop starting in the foreground."""
    global stop_requested
    
    if not worker_id:
        worker_id = str(uuid.uuid4())
        
    register_worker(worker_id)
    print(f"Worker {worker_id} started (PID: {os.getpid()})...")
    
    # Start heartbeat thread
    stop_event = threading.Event()
    t = threading.Thread(target=heartbeat_daemon, args=(worker_id, stop_event), daemon=True)
    t.start()
    
    # Load backoff configuration base
    backoff_base = 2.0
    with get_connection() as conn:
        cursor = conn.execute("SELECT value FROM config WHERE key = 'backoff-base'")
        row = cursor.fetchone()
        if row:
            backoff_base = float(row["value"])

    try:
        while not stop_requested:
            # Periodically recover orphaned jobs from other crashed workers
            try:
                recover_orphaned_jobs()
            except Exception as e:
                print(f"[{worker_id}] Recovery warning: {str(e)}", file=sys.stderr)
                
            # Check remote stop signal
            if check_remote_stop(worker_id):
                print(f"Worker {worker_id} stopping due to remote stop signal.")
                break
                
            # Attempt to claim a job atomically
            now_str = datetime.utcnow().isoformat() + "Z"
            job = claim_job_atomic(worker_id, now_str)
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
            else:
                # Sleep if no jobs
                time.sleep(1)
    finally:
        print(f"Worker {worker_id} shutting down cleanly...")
        # Stop the heartbeat thread
        stop_event.set()
        t.join(timeout=2.0)
        clean_worker_db(worker_id)
