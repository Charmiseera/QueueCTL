# QueueCTL - CLI Background Job Queue

QueueCTL is a lightweight, production-grade, CLI-driven background job queue built entirely using Python 3.11's standard library. It manages background job enqueuing, concurrent multi-worker processing, automatic exponential backoffs, crash recovery (SIGKILL resilience), and a Dead Letter Queue (DLQ).

---

## Features

- **Zero-Dependency Installation:** Implemented using only Python standard library components (`sqlite3`, `subprocess`, `argparse`, `signal`, `threading`).
- **Concurrent Processing:** Supports multiple parallel workers running in separate processes/terminal sessions.
- **Process-Safe Claiming:** Uses SQLite `BEGIN IMMEDIATE TRANSACTION` exclusive write locking to prevent duplicate claims.
- **Resilient Heartbeat Daemon:** Updates heartbeat check-ins in a background thread to prevent timeouts during long job execution.
- **Crash Recovery:** Automatically detects and recovers crashed workers' jobs in under 16 seconds.
- **Configurable Backoff & Retries:** Allows modifying retries and backoff base dynamically via CLI.

---

## Setup Instructions

Ensure Python 3.11+ is installed. Clone the repository and execute commands directly:

```bash
# Verify python version
python --version
```

No package installations are necessary!

---

## CLI Usage Reference

### 1. Enqueue a Job
Enqueue a JSON payload containing the job `id` and the `command` to execute:
```bash
python src/cli/main.py enqueue '{"id": "job-1", "command": "echo hello"}'
```

### 2. Start Workers
Start workers in the foreground (blocks until stopped). To run multiple worker processes in parallel from a single command:
```bash
python src/cli/main.py worker start --count 3
```

### 3. Stop Workers
Stop all active workers gracefully from another terminal session:
```bash
python src/cli/main.py worker stop
```

### 4. List Jobs
List jobs filtered by state (`pending`, `processing`, `completed`, `failed`, `dead`):
```bash
python src/cli/main.py list --state pending
```
To print strictly as a JSON array (useful for integration):
```bash
python src/cli/main.py list --state pending --json
```

### 5. Dead Letter Queue (DLQ)
List dead jobs:
```bash
python src/cli/main.py dlq list
```
Retry a job from the DLQ (resets attempts to 0):
```bash
python src/cli/main.py dlq retry job-1
```

### 6. Queue Status
Show a summary of all job states and active workers:
```bash
python src/cli/main.py status
```

### 7. Configuration
Dynamically set queue properties:
```bash
python src/cli/main.py config set max-retries 5
python src/cli/main.py config set backoff-base 3.0
```

---

## System Architecture

```
                                  +-------------------+
                                  |   QueueCTL CLI    |
                                  +---------+---------+
                                            |
                         +------------------+------------------+
                         |                                     |
                         v                                     v
               +-------------------+                 +-------------------+
               |   Queue Service   |                 |  Worker Service   |
               +---------+---------+                 +---------+---------+
                         |                                     |
                         |        +-------------------+        |
                         +------->|   SQLite DB WAL   |<-------+
                                  +-------------------+
```

- **Persistence Layer:** SQLite database located at `src/queuectl.db`. WAL (Write-Ahead Logging) is enabled for fast, concurrent read/write transactions.
- **Atomic claiming:** Utilizes SQLite's `BEGIN IMMEDIATE` transaction locking to guarantee mutually exclusive claims.
- **Heartbeat Thread:** Workers check in every 5 seconds via a separate daemon thread to ensure they are marked alive even while waiting on long commands.

---

## Testing

Run the complete test suite (unit tests, contract CLI tests, concurrency integration tests, and crash recovery tests):

```bash
python -m unittest discover -s tests
```
