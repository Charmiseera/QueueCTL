# Interface Contract: QueueCTL CLI

This document defines the interface contracts for the `queuectl` command-line utility.

## CLI Command Interface

All interaction with the queuectl engine is managed through the CLI interface.

### 1. Enqueue Job
Adds a new job to the queue.
- **Syntax**: `queuectl enqueue '<JSON>'`
- **Arguments**: A valid JSON string containing:
  - `id` (string, required): A unique job identifier.
  - `command` (string, required): The shell command to run.
  - `max_retries` (integer, optional): Override the default maximum retries.
- **Example**:
  ```bash
  queuectl enqueue '{"id":"job1","command":"echo hello"}'
  ```

---

### 2. Start Workers
Starts worker instances in the foreground to consume and execute queued jobs.
- **Syntax**: `queuectl worker start [--count <num>]`
- **Flags**:
  - `--count <num>` (integer, optional): The number of concurrent worker threads or subprocesses to spin up (default: 1).
- **Behavior**:
  - Runs in the foreground (blocks until stopped).
  - Handles SIGTERM / SIGINT (Ctrl+C) for graceful shutdown.
- **Example**:
  ```bash
  queuectl worker start --count 3
  ```

---

### 3. Stop Workers
Gracefully signals all active running workers to stop execution.
- **Syntax**: `queuectl worker stop`
- **Behavior**:
  - Sets the `should_stop = 1` flag in the database/configuration.
  - Commands workers to finish their in-flight jobs and exit.
- **Example**:
  ```bash
  queuectl worker stop
  ```

---

### 4. Queue Status
Displays a high-level summary of active workers and jobs.
- **Syntax**: `queuectl status`
- **Output Format**: Text summary showing counts of jobs by state (pending, processing, completed, failed, dead).
- **Example**:
  ```text
  Pending: 3 | Processing: 1 | Completed: 12 | Failed: 2 | Dead: 0
  Active Workers: 3
  ```

---

### 5. List Jobs
Lists jobs filtered by their current state.
- **Syntax**: `queuectl list --state <state> [--json]`
- **Parameters**:
  - `--state <state>` (required): One of `pending`, `processing`, `completed`, `failed`, `dead`.
  - `--json` (optional): If provided, the command **MUST** print a valid JSON array of job objects to stdout and nothing else.
- **Example (Standard Output)**:
  ```bash
  queuectl list --state pending
  ```
- **Example (JSON Output)**:
  ```bash
  queuectl list --state pending --json
  ```
  *Output*:
  ```json
  [
    {
      "id": "job1",
      "command": "sleep 2",
      "state": "pending",
      "attempts": 0,
      "max_retries": 3,
      "created_at": "2026-07-29T12:00:00Z",
      "updated_at": "2026-07-29T12:00:00Z"
    }
  ]
  ```

---

### 6. List DLQ
Lists all jobs currently quarantined in the Dead Letter Queue.
- **Syntax**: `queuectl dlq list`
- **Behavior**: Equivalent to `queuectl list --state dead`.

---

### 7. Retry DLQ Job
Re-queues a failed job from the Dead Letter Queue.
- **Syntax**: `queuectl dlq retry <id>`
- **Behavior**:
  - Resets the target job's state to `pending`.
  - Resets the `attempts` counter to `0`.
  - Clears worker associations and schedules it to run immediately.

---

### 8. System Configuration
Configures retry and delay options dynamically.
- **Syntax**: `queuectl config set <key> <value>`
- **Supported Keys**:
  - `max-retries` (integer): Default max retries for new jobs.
  - `backoff-base` (number): Exponential base for retry calculations.

---

## Signal Handling and Execution Contracts

### Ctrl+C / SIGINT & SIGTERM
- When the worker process receives SIGINT/SIGTERM, it must not terminate immediately.
- It must await the completion of the command currently running in its subprocess.
- Once completed, it writes the final job state (`completed` or `failed`), registers its exit, and terminates cleanly.

### CLI Exit Codes
- Success: `0`
- Invalid commands or bad arguments: `1`
- Execution/Queue runtime error: `2`
