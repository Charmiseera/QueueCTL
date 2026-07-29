# QueueCTL System Design Decisions

This document details the architectural decisions and answers to the five mandatory design questions for QueueCTL.

---

### 1. Atomic Job Claiming across OS Processes

**Exact Line of Atomicity:**
The atomic claiming mechanism is defined in [db_service.py](file:///d:/Flam/src/services/db_service.py#L74):
```python
conn.execute("BEGIN IMMEDIATE TRANSACTION;")
```

**Why it is atomic across separate OS processes:**
SQLite uses database file locks to serialize transaction access. 
- Using `BEGIN IMMEDIATE` locks the database exclusively for write transactions.
- If multiple worker processes try to claim a job at the exact same moment, only one worker will successfully acquire the lock.
- Any concurrent workers attempting to execute `BEGIN IMMEDIATE` will immediately receive an `sqlite3.OperationalError` (database is locked), which we catch and gracefully return `None` (no job claimed).
- Inside the transaction block, the winning worker selects the first eligible job (`state='pending'` or `state='failed'`) and updates its state to `processing` and its `worker_id` to its own ID before committing the transaction and releasing the database lock. This ensures no two processes can ever select or run the same job.

---

### 2. SIGKILL Crash Recovery Scenario

**Step-by-Step Recovery Workflow:**
1. **Worker Crashes:** When a worker is killed via `SIGKILL`, the process terminates immediately without executing Python cleanups or signal handlers.
2. **Current State:** The database retains the job state as `processing` and preserves the associated crashed worker's `worker_id`.
3. **Detection:** All active workers periodically invoke `recover_orphaned_jobs()` at the beginning of each loop iteration. This function retrieves all registered workers and check their `last_heartbeat`.
4. **Recovery Trigger:** Because the crashed worker is no longer running, its heartbeat timestamp remains stagnated. Once another active worker detects a worker whose heartbeat is older than 15 seconds, it identifies it as dead.
5. **Job Reset:** The active worker resets any jobs marked as `processing` on that dead worker back to `pending`, clears their `worker_id`, sets `run_at` to the current time, and deletes the dead worker's row from the database.
6. **Execution:** On the next iteration, an active worker picks up the job and executes it to completion.

**Worst-case delay before recovery:**
- The heartbeat timeout threshold is **15 seconds**.
- Idle workers check for jobs and recover orphans every **1 second**.
- Therefore, the absolute worst-case delay before a crashed job is reset and picked up is **16 seconds** (`15s timeout + 1s loop sleep`), well within the required 60-second limit.

---

### 3. DLQ Retry attempts Counter Reset

**Decision:**
Yes, invoking `dlq retry <id>` resets the `attempts` counter back to `0`.

**Justification:**
Moving a job to the DLQ (`dead` state) indicates that the job has exhausted all of its `max_retries` due to persistent failure. By manually running `dlq retry`, a system administrator is explicitly indicating that they have diagnosed and resolved the issue (e.g. fixed a missing configuration, network interface, or code bug).
- Resetting `attempts` to `0` gives the job a completely fresh retry budget.
- If the job fails again after being re-enqueued, it will follow the full exponential backoff schedule rather than immediately returning to the DLQ on its first failure.

---

### 4. Rejected Worker Stop Signaling Designs

* **Rejected: OS Signals (`kill` / PID signaling):** Sending a signal directly to the worker PIDs is highly platform-dependent (Windows handles signals completely differently from Unix and lacks standard signals like SIGTERM/SIGUSR). It also runs the risk of cutting off the worker mid-job if not handled with care.
* **Rejected: Local TCP / IPC sockets:** Opening a local listener socket per worker process introduces complexity with port management, local firewalls, socket resource leaks, and Windows compatibility issues.
* **Chosen Design: Database-backed signals:** The `worker stop` command updates a persistent `should_stop = 1` field in the database `workers` table. Active workers inspect this flag at the start of every iteration. This is 100% platform-independent, requires no port management, and guarantees graceful shutdowns because workers finish their in-progress job before checking the stop flag and exiting.

---

### 5. Adding Job Priorities Tomorrow

**Surviving Unchanged:**
- SQLite database initialization (`init_db`) and connection configuration.
- The worker registration, heartbeat tracking daemon, and signaling mechanism.
- The subprocess execution logic (`run_job`).
- The config management subsystem.

**Breaking / Requiring Changes:**
- **Database Schema:** We would need to add a `priority` column to the `jobs` table (e.g. `priority INTEGER DEFAULT 0`).
- **Claim Logic:** The SQL query inside `claim_job_atomic` would need to update its ordering criteria:
  ```sql
  ORDER BY priority DESC, created_at ASC
  ```
- **CLI Commands:** The `enqueue` command parsing would need to accept an optional priority key in the JSON payload (e.g., `{"id": "job1", "command": "cmd", "priority": 10}`).
