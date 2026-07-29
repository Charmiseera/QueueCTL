# Feature Specification: QueueCTL Job Queue

**Feature Branch**: `001-queuectl-job-queue`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description from [assignment.md](file:///d:/Flam/assignment.md)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Job Enqueue & Execution (Priority: P1)
As an operator, I want to submit jobs to the queue via the CLI and have them executed by a worker process so that jobs run in the background.

**Why this priority**: Core value of the queue system. Without this, no background processing can occur.

**Independent Test**:
A single worker is started. A shell command job is enqueued. The worker picks up the job, runs the shell command, redirects execution output appropriately, and updates the job status to `completed` upon exit code 0.

**Acceptance Scenarios**:
1. **Given** no jobs exist in the queue, **When** I run `queuectl enqueue '{"id":"job1","command":"echo hello"}'`, **Then** the job is stored with state `pending`.
2. **Given** a job `job1` with state `pending` exists, **When** a worker process runs, **Then** the worker claims the job, updates its state to `processing`, executes `echo hello`, and transitions the state to `completed` upon success.
3. **Given** a job `job1` is in `completed` state, **When** I run `queuectl list --state completed --json`, **Then** it prints a JSON array containing the job details to stdout.

---

### User Story 2 - Automatic Retries & DLQ Management (Priority: P1)
As an operator, I want failed jobs to be automatically retried with exponential backoff, and eventually moved to a Dead Letter Queue (DLQ) if they keep failing, so that transient errors are self-healed and permanent failures are quarantined.

**Why this priority**: Critical for system reliability. Ensures temporary issues (network blips, etc.) do not cause permanent loss, while isolating permanent errors.

**Independent Test**:
A job with a command that exits with a non-zero code is enqueued. The worker runs the job, records the failure, waits for the backoff duration to elapse, retries it up to the configured limit, and then moves the job to the DLQ state (`dead`).

**Acceptance Scenarios**:
1. **Given** a job with `max_retries` of 2, **When** the job fails its execution, **Then** it is updated to `failed`, and its retry is scheduled after `base ^ attempts` seconds.
2. **Given** a job has reached its maximum retries and fails again, **When** the execution fails, **Then** the job state transitions to `dead` (DLQ).
3. **Given** a job is in `dead` state, **When** I run `queuectl dlq retry <id>`, **Then** the job state resets to `pending`, its attempts counter resets to 0, and it is placed back in the queue.

---

### User Story 3 - Concurrent Multi-Worker Execution (Priority: P1)
As an administrator, I want to run multiple worker processes in parallel from separate terminal sessions without them executing the same job twice.

**Why this priority**: Scale and throughput. Allows parallel execution of independent tasks while maintaining strict single-execution guarantees.

**Independent Test**:
Start three worker processes in separate terminals. Enqueue 20 jobs. Verify that all 20 jobs are executed exactly once and no job is run by more than one worker.

**Acceptance Scenarios**:
1. **Given** multiple workers are running, **When** multiple `pending` jobs are in the queue, **Then** workers claim jobs concurrently using an atomic process-safe locking operation.
2. **Given** a job is currently claimed and in `processing` by Worker A, **When** Worker B checks the queue, **Then** Worker B must bypass that job and select another `pending` job.

---

### User Story 4 - Crash Recovery & SIGKILL Resilience (Priority: P1)
As an operator, I want the system to automatically recover and rerun jobs that were interrupted mid-execution due to a worker crash or SIGKILL.

**Why this priority**: Crucial for robustness. Prevents jobs from getting stuck in `processing` indefinitely when workers crash, ensuring eventual completion of all work.

**Independent Test**:
A worker is started and begins executing a long-running job. The worker process is killed via SIGKILL. A new worker is started or the recovery loop runs, detecting the orphaned job and resetting it to `pending` so it can be re-executed.

**Acceptance Scenarios**:
1. **Given** a job is in `processing` state, **When** the worker executing it dies abruptly, **Then** the system detects that the worker is no longer active within 60 seconds.
2. **Given** an orphaned job is detected, **When** the recovery mechanism runs, **Then** the job state is reset to `pending` (or `failed` if it counts as an attempt) so that it can be picked up again by an active worker.

---

### User Story 5 - CLI Configuration Management (Priority: P2)
As an operator, I want to view and update system configurations (like `max_retries` and `backoff_base`) dynamically via the CLI.

**Why this priority**: Operability and tuning. Allows adjustment of backoff and retry behavior without modifying source code or stopping the system.

**Independent Test**:
Run configuration CLI commands to view and modify settings, then verify that newly enqueued jobs inherit these updated parameters.

**Acceptance Scenarios**:
1. **Given** a system with default configurations, **When** I run `queuectl config set max-retries 5`, **Then** the new default `max_retries` for subsequently enqueued jobs becomes 5.
2. **Given** a custom configuration is set, **When** the queuectl CLI or worker restarts, **Then** the custom configuration is loaded and applied.

---

### Edge Cases

- **Command Not Found**: If a job command is invalid or executable does not exist, the worker must capture the error, exit with a failure code, and transition the job to `failed` to trigger retries.
- **Concurrent Signal Interruption**: If the worker process receives SIGTERM/SIGINT during a job execution, it must wait for the command subprocess to complete, update the status, and then terminate gracefully.
- **Database/File Locking Contention**: When multiple workers attempt to lock and read the database/file at the exact same millisecond, the database driver or file lock must queue the requests or handle retries gracefully without crashing.
- **Clock Drift**: Backoff timers rely on timestamps. The system should handle reasonable clock variation or relative durations to avoid scheduling errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: **CLI Command Surface**: The system must provide a single binary or script `queuectl` supporting:
  - `queuectl enqueue '<JSON>'`
  - `queuectl worker start [--count <num>]`
  - `queuectl worker stop`
  - `queuectl status`
  - `queuectl list --state <state> [--json]`
  - `queuectl dlq list`
  - `queuectl dlq retry <id>`
  - `queuectl config set <key> <value>`
- **FR-002**: **Strict Output Contract**: The command `queuectl list --state <state> --json` must write a valid JSON array of job objects to stdout and nothing else (no logs, headers, or debug output on stdout).
- **FR-003**: **Process-Safe Concurrency**: The system must support running workers in separate OS processes. The claim-job operation must be atomic across processes to prevent a job from being executed by more than one worker.
- **FR-004**: **Persistent Job Storage**: All job state, metadata, and execution history must survive worker and CLI restarts.
- **FR-005**: **Graceful Worker Shutdown**: Upon receiving SIGINT or SIGTERM, a running worker must wait for its active subprocess command to finish executing, update the job state, and then terminate.
- **FR-006**: **Resilience and Orphan Recovery**: The system must monitor worker health or inspect active runs. If a worker dies (SIGKILL), the job must be detected as orphaned and recovered to `pending` status in under 60 seconds.
- **FR-007**: **Exponential Backoff**: Retries must occur after `base ^ attempts` seconds of delay. The `base` must default to 2 and be configurable via `config set backoff-base`.
- **FR-008**: **DLQ Migration**: After `max_retries` are exhausted, the job's state must change to `dead` (DLQ). Retrying a dead job resets its attempt counter to 0.

### Key Entities *(include if data involved)*

- **Job**: Represents a background task.
  - `id` (string): Unique identifier.
  - `command` (string): Shell command to execute.
  - `state` (string): State of the job (`pending`, `processing`, `completed`, `failed`, `dead`).
  - `attempts` (integer): Number of completed execution attempts.
  - `max_retries` (integer): Maximum retries allowed.
  - `created_at` (timestamp): ISO 8601 creation time.
  - `updated_at` (timestamp): ISO 8601 last update time.
- **Worker**: Represents a worker process or thread pool execution slot.
  - `id` (string): Unique identifier (e.g. process ID or UUID).
  - `last_heartbeat` (timestamp): Last time the worker checked in, used to identify crashed workers.
- **Configuration**: Represents system-wide settings.
  - `max_retries` (integer): Default retries for new jobs.
  - `backoff_base` (integer): Exponential base for retry delay.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Interface Compliance**: The CLI output for `queuectl list --state <state> --json` parses as valid JSON matching the schema requirements without manual modification.
- **SC-002**: **No Stuck Jobs**: 100% of jobs interrupted by worker SIGKILL are automatically recovered and resume execution in less than 60 seconds.
- **SC-003**: **Zero Duplicate Executions**: Under concurrent loads of 20+ parallel tasks across 3+ workers, no job is executed more than once.
- **SC-004**: **Graceful Stop Delay**: On SIGINT/SIGTERM, the worker processes terminate only after their active job command finishes (up to the job command's execution time limit).
- **SC-005**: **Correct Backoff Intervals**: Retried jobs are executed with delays matching `base ^ attempts` seconds (within a 10% margin of timing error).

## Assumptions

- **Subprocess Environment**: The host OS environment has a shell (bash/cmd/powershell) capable of running the enqueued commands.
- **No Complex Output Capturing**: The stdout/stderr outputs of the job's command are not required to be saved inside the job queue state itself, unless logging features are implemented.
- **Single DB File / Shared Storage**: Workers run on the same physical machine or have access to a shared file system (or DB) enabling file/table locks.
- **CLI Discovery**: The CLI is able to communicate with workers via shared persistent storage, lock files, or process IDs.
