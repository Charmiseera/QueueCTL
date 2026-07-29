from datetime import datetime

class Job:
    def __init__(self, id, command, state="pending", attempts=0, max_retries=3, worker_id=None, run_at=None, created_at=None, updated_at=None):
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

    @classmethod
    def from_row(cls, row):
        """Creates a Job instance from a SQLite Row or dictionary."""
        return cls(
            id=row["id"],
            command=row["command"],
            state=row["state"],
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            worker_id=row["worker_id"],
            run_at=row["run_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
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
            "updated_at": self.updated_at
        }
