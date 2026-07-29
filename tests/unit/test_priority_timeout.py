import unittest
import sys
import os
import time
from datetime import datetime
from src.services.db_service import get_connection, init_db, claim_job_atomic
from src.services.queue_service import enqueue_job, list_jobs
from src.services.worker_service import run_job, update_job_status
from src.models.job import Job

class TestPriorityAndTimeout(unittest.TestCase):
    def setUp(self):
        # Drop table to ensure clean state
        try:
            with get_connection() as conn:
                conn.execute("DROP TABLE IF EXISTS jobs;")
                conn.execute("DROP TABLE IF EXISTS workers;")
                conn.execute("DROP TABLE IF EXISTS config;")
                conn.commit()
        except:
            pass
        init_db()

    def tearDown(self):
        try:
            with get_connection() as conn:
                conn.execute("DROP TABLE IF EXISTS jobs;")
                conn.execute("DROP TABLE IF EXISTS workers;")
                conn.execute("DROP TABLE IF EXISTS config;")
                conn.commit()
        except:
            pass

    def test_priority_claiming(self):
        # 1. Enqueue lower priority job first
        enqueue_job("low-prio", "echo low", priority=0)
        
        # 2. Enqueue higher priority job second
        enqueue_job("high-prio", "echo high", priority=10)
        
        # 3. Register worker to satisfy foreign key constraint and atomically claim a job
        from src.services.worker_service import register_worker
        register_worker("worker-1")
        now_str = datetime.utcnow().isoformat() + "Z"
        job = claim_job_atomic("worker-1", now_str)
        
        # 4. Verify that the higher priority job was claimed first
        self.assertIsNotNone(job)
        self.assertEqual(job.id, "high-prio")

    def test_job_timeout(self):
        # 1. Enqueue a job that takes 4 seconds but has a 1-second timeout
        # Using cross-platform command (python sleep)
        cmd = f"{sys.executable} -c \"import time; time.sleep(4)\""
        job = Job(
            id="job-timeout-test",
            command=cmd,
            timeout=1
        )
        
        # 2. Run the job
        retcode, stdout, stderr = run_job(job)
        
        # 3. Verify it was terminated due to timeout (exit code -2)
        self.assertEqual(retcode, -2)
        self.assertIn("exceeded timeout limit", stderr)

if __name__ == "__main__":
    unittest.main()
