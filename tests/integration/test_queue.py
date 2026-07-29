import unittest
import subprocess
import sys
import json
import os
import time
from src.services.db_service import DB_PATH, get_connection
from src.services.queue_service import enqueue_job, list_jobs

class TestQueueIntegration(unittest.TestCase):
    def setUp(self):
        # Clean DB tables instead of deleting the locked file
        from src.services.db_service import get_connection
        try:
            with get_connection() as conn:
                conn.execute("DROP TABLE IF EXISTS jobs;")
                conn.execute("DROP TABLE IF EXISTS workers;")
                conn.execute("DROP TABLE IF EXISTS config;")
                conn.commit()
        except:
            pass

    def tearDown(self):
        self.setUp()

    def test_concurrent_multi_workers(self):
        # 1. Enqueue 20 jobs that write their execution to a temporary log file
        log_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "test_run.log"))
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
            except:
                pass

        # We want to use a command that appends job ID to log_file
        # Cross-platform command in python to append to log_file
        py_cmd = f"import sys; f=open('{log_file.replace(os.sep, '/')}', 'a'); f.write(sys.argv[1] + '\\n'); f.close()"
        
        for i in range(20):
            job_id = f"job-concur-{i}"
            cmd_str = f"{sys.executable} -c \"{py_cmd}\" {job_id}"
            enqueue_job(job_id, cmd_str, max_retries=1)

        # 2. Start 3 worker processes
        workers = []
        for _ in range(3):
            # start worker in foreground (will block)
            p = subprocess.Popen(
                [sys.executable, "src/cli/main.py", "worker", "start"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            workers.append(p)

        # Give them time to process all 20 jobs (approx 5-10s)
        time.sleep(8)

        # 3. Stop workers using CLI stop
        stop_res = subprocess.run(
            [sys.executable, "src/cli/main.py", "worker", "stop"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(stop_res.returncode, 0)

        # Wait for processes to exit
        for w in workers:
            try:
                w.wait(timeout=5)
            except subprocess.TimeoutExpired:
                w.terminate()

        # 4. Verify completed jobs
        jobs = list_jobs("completed")
        self.assertEqual(len(jobs), 20)

        # 5. Read log file to ensure every job ran EXACTLY once
        self.assertTrue(os.path.exists(log_file), "Log file was not created!")
        with open(log_file, "r") as f:
            runs = [line.strip() for line in f if line.strip()]
        
        self.assertEqual(len(runs), 20)
        self.assertEqual(len(set(runs)), 20) # Unique count must be 20

        # Clean up log file
        try:
            os.remove(log_file)
        except:
            pass

    def test_crash_recovery(self):
        # 1. Enqueue a job
        enqueue_job("job-crash-test", "echo crash_recovered", max_retries=2)
        
        # 2. Start worker and allow it to claim it, then SIGKILL it
        # To simulate a worker crashing mid-job, we can register a worker and mark the job as processing
        from src.services.db_service import get_connection
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        now_str = now.isoformat() + "Z"
        # Simulate worker check-in 20 seconds ago (expired heartbeat)
        expired_hb_str = (now - timedelta(seconds=20)).isoformat() + "Z"
        
        with get_connection() as conn:
            # Register worker with expired heartbeat
            conn.execute("""
            INSERT INTO workers (id, pid, last_heartbeat, should_stop)
            VALUES ('worker-dead-1', 99999, ?, 0);
            """, (expired_hb_str,))
            
            # Associate job with this dead worker and set state to processing
            conn.execute("""
            UPDATE jobs
            SET state = 'processing', worker_id = 'worker-dead-1', updated_at = ?, attempts = 1
            WHERE id = 'job-crash-test';
            """, (now_str,))
            conn.commit()
            
        # 3. Running recover_orphaned_jobs should reset the job to pending
        from src.services.queue_service import recover_orphaned_jobs
        recover_orphaned_jobs()
        
        # 4. Verify job is pending again
        jobs = list_jobs("pending")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].id, "job-crash-test")
        self.assertIsNone(jobs[0].worker_id)
        
        # 5. Start worker to complete the job
        p = subprocess.Popen(
            [sys.executable, "src/cli/main.py", "worker", "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(3)
        # Stop worker
        subprocess.run([sys.executable, "src/cli/main.py", "worker", "stop"])
        p.wait(timeout=5)
        
        # Verify job is completed
        completed_jobs = list_jobs("completed")
        self.assertEqual(len(completed_jobs), 1)
        self.assertEqual(completed_jobs[0].id, "job-crash-test")

if __name__ == "__main__":
    unittest.main()
