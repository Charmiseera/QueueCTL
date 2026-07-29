from datetime import datetime

class Job:
    def __init__(self, id, command, state="pending", attempts=0, max_retries=3, worker_id=None, run_at=None, created_at=None, updated_at=None, priority=0, timeout=60, stdout=None, stderr=None):
        self.id = id
        self.command = command
        self.state = state
        self.attempts = attempts
        self.max_retries = max_retries
        self.worker_id = worker_id
        
        now_str = datetime.utcnow().isoformat() + "Z"
        self.run_at = run_at or now_str
        self.created_at = created_at or now_str
        self.updated_at = updated_at or now_str
        self.priority = priority
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr

    @classmethod
    def from_row(cls, row):
        """Creates a Job instance from a SQLite Row or dictionary."""
        # Check keys to be backward-compatible with older schemas if columns missing
        row_keys = row.keys() if hasattr(row, "keys") else row
        priority = row["priority"] if "priority" in row_keys else 0
        timeout = row["timeout"] if "timeout" in row_keys else 60
        stdout = row["stdout"] if "stdout" in row_keys else None
        stderr = row["stderr"] if "stderr" in row_keys else None
        
        return cls(
            id=row["id"],
            command=row["command"],
            state=row["state"],
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            worker_id=row["worker_id"],
            run_at=row["run_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            priority=priority,
            timeout=timeout,
            stdout=stdout,
            stderr=stderr
        )

    def to_dict(self):
        """Converts Job into a dictionary matching the spec schema."""
        return {
            "id": self.id,
            "command": self.command,
            "state": self.state,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "priority": self.priority,
            "timeout": self.timeout,
            "stdout": self.stdout,
            "stderr": self.stderr
        }

    def calculate_delay(self, backoff_base=2.0):
        """Calculates backoff delay in seconds: base ^ attempts."""
        return float(backoff_base) ** self.attempts

