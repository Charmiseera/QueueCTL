from datetime import datetime

class Worker:
    def __init__(self, id, pid, last_heartbeat=None, should_stop=0):
        self.id = id
        self.pid = pid
        self.last_heartbeat = last_heartbeat or datetime.utcnow().isoformat() + "Z"
        self.should_stop = should_stop

    @classmethod
    def from_row(cls, row):
        """Creates a Worker instance from a SQLite Row or dictionary."""
        return cls(
            id=row["id"],
            pid=row["pid"],
            last_heartbeat=row["last_heartbeat"],
            should_stop=row["should_stop"]
        )

    def to_dict(self):
        """Converts Worker into a dictionary."""
        return {
            "id": self.id,
            "pid": self.pid,
            "last_heartbeat": self.last_heartbeat,
            "should_stop": self.should_stop
        }
