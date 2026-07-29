import unittest
from datetime import datetime
from src.models.job import Job

class TestJobModel(unittest.TestCase):
    def test_job_defaults(self):
        job = Job(id="job-1", command="echo hello")
        self.assertEqual(job.id, "job-1")
        self.assertEqual(job.command, "echo hello")
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.max_retries, 3)
        self.assertIsNone(job.worker_id)
        self.assertTrue(job.run_at.endswith("Z"))
        self.assertTrue(job.created_at.endswith("Z"))
        self.assertTrue(job.updated_at.endswith("Z"))

    def test_job_to_dict(self):
        job = Job(id="job-2", command="echo success", state="completed", attempts=1, max_retries=5)
        d = job.to_dict()
        self.assertEqual(d["id"], "job-2")
        self.assertEqual(d["command"], "echo success")
        self.assertEqual(d["state"], "completed")
        self.assertEqual(d["attempts"], 1)
        self.assertEqual(d["max_retries"], 5)
        self.assertIn("created_at", d)
        self.assertIn("updated_at", d)
        self.assertNotIn("worker_id", d) # worker_id should not leak to public dict output per contract
        self.assertNotIn("run_at", d)

    def test_job_from_row(self):
        row = {
            "id": "job-3",
            "command": "sleep 1",
            "state": "failed",
            "attempts": 2,
            "max_retries": 3,
            "worker_id": "worker-xyz",
            "run_at": "2026-07-29T12:00:00Z",
            "created_at": "2026-07-29T11:50:00Z",
            "updated_at": "2026-07-29T11:55:00Z"
        }
        job = Job.from_row(row)
        self.assertEqual(job.id, "job-3")
        self.assertEqual(job.command, "sleep 1")
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.attempts, 2)
        self.assertEqual(job.max_retries, 3)
        self.assertEqual(job.worker_id, "worker-xyz")
        self.assertEqual(job.run_at, "2026-07-29T12:00:00Z")
        self.assertEqual(job.created_at, "2026-07-29T11:50:00Z")
        self.assertEqual(job.updated_at, "2026-07-29T11:55:00Z")

    def test_calculate_delay(self):
        job = Job(id="job-4", command="echo delay")
        job.attempts = 1
        self.assertEqual(job.calculate_delay(2.0), 2.0)
        job.attempts = 2
        self.assertEqual(job.calculate_delay(2.0), 4.0)
        job.attempts = 3
        self.assertEqual(job.calculate_delay(2.0), 8.0)
        # Verify custom base
        job.attempts = 2
        self.assertEqual(job.calculate_delay(3.0), 9.0)

if __name__ == "__main__":
    unittest.main()
