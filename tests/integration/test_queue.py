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
        # Fresh DB before each test
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except:
                pass
            if os.path.exists(DB_PATH + "-wal"):
                try:
                    os.remove(DB_PATH + "-wal")
                except:
                    pass
            if os.path.exists(DB_PATH + "-shm"):
                try:
                    os.remove(DB_PATH + "-shm")
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

if __name__ == "__main__":
    unittest.main()
