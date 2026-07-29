# Research Notes: QueueCTL Job Queue

This document outlines the key design decisions, trade-offs, and technical solutions for implementing the QueueCTL background job queue.

## Concurrency and Atomic Job Claiming

### Decision
Use SQLite as the persistent storage engine. Concurrency and atomic claiming will be achieved using SQLite's file-locking and immediate transaction capabilities.

### Rationale
- SQLite is self-contained, requires no separate server processes to be managed (highly suitable for a student assignment), and is cross-process safe since the operating system enforces file locks.
- An update query executed inside a transaction with `BEGIN IMMEDIATE` ensures that only one worker process can acquire a write lock and claim a specific job.

### Query for Atomic Claim
```sql
BEGIN IMMEDIATE TRANSACTION;

-- Find the next eligible pending job
UPDATE jobs
SET state = 'processing',
    worker_id = ?,
    updated_at = ?,
    attempts = attempts + 1
WHERE id = (
    SELECT id FROM jobs
    WHERE state = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
);

COMMIT;
```
If two workers execute this simultaneously, one transaction will acquire the write lock first, and the other transaction will wait or fail with a busy error (which we can retry after a short delay). This prevents duplicate execution.

### Alternatives Considered
- **File System Locking (lock files)**: Storing jobs in separate JSON files and using OS-level file locks (`flock` on Unix or `msvcrt.locking` on Windows). *Rejected because* database transactions are cleaner, transactional updates across multiple fields are simpler, and SQLite handles cross-platform locking natively.
- **IPC sockets/Server process**: Running a central daemon that listens on a Unix socket or TCP port. *Rejected because* it increases complexity and violates the simplicity of the CLI-only command contract.

---

## Crash Recovery and SIGKILL Resilience

### Decision
Implement a heartbeat-based worker tracking mechanism in SQLite. When a worker process executes `worker start`, it generates a UUID and registers itself in a `workers` table, periodically updating its `last_heartbeat` timestamp (every 5 seconds).

### Step-by-Step Recovery Flow after SIGKILL
1. **Worker is SIGKILLed**: The worker process dies instantly. The job state remains `processing` in the database, associated with the dead worker's ID.
2. **Orphan Detection**: A recovery task (run at the start of any new worker loop iteration or by a periodic check) scans the `jobs` table for jobs with state `processing` whose associated worker's `last_heartbeat` is older than 15 seconds.
3. **Job Re-queuing**: The recovery task:
   - Sets the job's state back to `pending` if its `attempts` is less than `max_retries`.
   - Moves it to `dead` (DLQ) if the attempts have run out.
   - Clears the job's worker association.
4. **Execution Resume**: An active worker picks up the reset `pending` job.

### Latency and Worst-Case Delay
- **Worker Heartbeat Interval**: 5 seconds.
- **Heartbeat Timeout Threshold**: 15 seconds.
- **Recovery Scan Interval**: Active workers scan for orphans every 10 seconds.
- **Worst-case Latency**: Under 30 seconds (well within the required 60 seconds limit).

---

## Graceful Stop Signaling

### Decision
Signal workers using direct OS signals (`SIGTERM`/`SIGINT` via Ctrl+C) combined with a database-backed execution control flag for remote commands like `queuectl worker stop`.

### Mechanics
- **Local Interruption (Ctrl+C)**: Python's `signal` module catches `SIGINT`. It sets an internal boolean flag `stop_requested = True`. The worker loop inspects this flag *after* the current subprocess execution finishes, then exits cleanly.
- **Remote Stopping (`worker stop`)**: When `queuectl worker stop` is executed from another terminal, it updates a global configuration or active worker state in the database (`should_stop = 1`). Workers query this state at the end of each job execution. If set, they clean up and exit.

---

## DLQ Retry Attempt Handling

### Decision
Executing `dlq retry <id>` will reset the `attempts` counter of the job back to `0`.

### Rationale
- When a job lands in the DLQ, it indicates a permanent failure after exhaustively retrying.
- Moving it out of the DLQ is a manual operator action. The operator is asserting that they have corrected the underlying issue (e.g. fixed a broken path, installed a missing utility, or updated configs).
- Resetting the attempts counter to 0 gives the job a full new cycle of retries under the standard exponential backoff configuration.

---

## Extensibility: Priority Queues

### Impact Analysis of Adding Job Priorities

| Component | Status | Required Changes |
|-----------|--------|------------------|
| CLI Command Surface | Unchanged | `queuectl enqueue` can optionally accept a `--priority` flag. |
| DB Schema | Unchanged | Add a `priority` column (integer, defaults to 0). |
| Concurrency Logic | **Changed** | The claim query must prioritize higher priority jobs first: `ORDER BY priority DESC, created_at ASC`. |
| Worker Exec Loop | Unchanged | Workers still run job commands exactly the same way. |
| Retry & Backoff | Unchanged | Delay calculation and DLQ migrations remain identical. |
