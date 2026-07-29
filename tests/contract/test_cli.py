import unittest
import subprocess
import sys
import json
import os
from src.services.db_service import DB_PATH

class TestCLIContract(unittest.TestCase):
    def setUp(self):
        # Remove DB file if exists to start fresh
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except:
                pass
            # Also clean WAL files
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

    def run_cli(self, args):
        cmd = [sys.executable, "src/cli/main.py"] + args
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result

    def test_enqueue_and_list_json(self):
        # 1. Enqueue job
        json_data = '{"id":"job-test-cli","command":"echo hello"}'
        res = self.run_cli(["enqueue", json_data])
        self.assertEqual(res.returncode, 0, msg=f"stdout: {res.stdout}\nstderr: {res.stderr}")
        
        # 2. List jobs --state pending --json
        res_list = self.run_cli(["list", "--state", "pending", "--json"])
        self.assertEqual(res_list.returncode, 0)
        
        # Verify stdout is strictly a JSON array and nothing else
        stdout_clean = res_list.stdout.strip()
        data = json.loads(stdout_clean)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "job-test-cli")
        self.assertEqual(data[0]["command"], "echo hello")
        self.assertEqual(data[0]["state"], "pending")
        self.assertEqual(data[0]["attempts"], 0)
        self.assertEqual(data[0]["max_retries"], 3)
        self.assertIn("created_at", data[0])
        self.assertIn("updated_at", data[0])

if __name__ == "__main__":
    unittest.main()
