# Implementation Plan: QueueCTL Job Queue

**Branch**: `001-queuectl-job-queue` | **Date**: 2026-07-29 | **Spec**: [spec.md](file:///d:/Flam/specs/001-queuectl-job-queue/spec.md)

**Input**: Feature specification from `specs/001-queuectl-job-queue/spec.md`

## Summary
The goal is to implement QueueCTL, a CLI-based background job queue system. The system manages background jobs, processes them concurrently across multiple terminal instances using parallel workers, handles execution failures with exponential backoff retries, and maintains a Dead Letter Queue (DLQ) for permanently failed jobs. The technical approach leverages Python's built-in standard library modules (`sqlite3`, `argparse`, `subprocess`, `signal`) to achieve database-backed process-safe transactions, atomic job claims, periodic heartbeat-based crash detection (SIGKILL recovery), and signal handling for graceful worker shutdown.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: None (Standard Library only to ensure compatibility, zero external installation issues, and clean grading)

**Storage**: SQLite 3 local database file (`queuectl.db` in repository root)

**Testing**: Python `unittest` standard library framework

**Target Platform**: Cross-platform (Windows / Linux / macOS)

**Project Type**: CLI tool & background worker

**Performance Goals**:
- Job claim database transaction latency under 20ms.
- Orphan/crash detection running checkins every 5 seconds.
- Recovery of crashed jobs (SIGKILLed workers) in under 30 seconds.

**Constraints**:
- Atomic job-claiming transactions to prevent dual worker claiming across OS processes.
- Heartbeat timeouts to identify worker crashes.
- Signal interception for graceful teardowns of running sub-commands.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **CLI-First**: Does the design adhere strictly to the CLI interface contract?
- [x] **Resilience**: Is there an automated recovery mechanism for crashed/SIGKILLed workers (recovery < 60s)?
- [x] **Concurrency**: Is the job-claiming operation atomic across separate OS processes?
- [x] **Retry/DLQ**: Are retry delays calculated via exponential backoff and jobs moved to DLQ after max retries?
- [x] **Documentation**: Are the five key decisions documented in DECISIONS.md?

## Project Structure

### Documentation (this feature)

```text
specs/001-queuectl-job-queue/
├── plan.md              # This file
├── research.md          # Technical research notes
├── data-model.md        # Database schema and states
├── quickstart.md        # Validation scenarios
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── contracts/
    └── cli.md           # CLI interface specifications
```

### Source Code (repository root)

```text
src/
├── cli/
│   ├── __init__.py
│   └── main.py          # Entrypoint parser and command router
├── models/
│   ├── __init__.py
│   ├── job.py           # Job entity logic and state representation
│   └── worker.py        # Worker heartbeat and registration model
├── services/
│   ├── __init__.py
│   ├── db_service.py    # SQLite connection initialization and migrations
│   ├── queue_service.py # Enqueue, status, config, and DLQ management
│   └── worker_service.py # Worker execution loops, concurrency claim, and recovery checks
└── config.py            # Global variables and configuration paths

tests/
├── contract/
│   └── test_cli.py      # Contract validation tests (runs real CLI inputs)
├── integration/
│   └── test_queue.py    # Multi-worker concurrency and crash recovery integration tests
└── unit/
    ├── test_models.py   # Unit tests for job status calculations and time offsets
    └── test_services.py # Unit tests for service queries
```

**Structure Decision**: Single Python project structure as laid out above. This encapsulates CLI parsing in `src/cli`, database/models in `src/models` and `src/services`, and separates tests cleanly into `tests/`.

## Complexity Tracking

No violations of project principles or architectural constraints. The design is kept highly minimal and relies entirely on Python's standard library to guarantee portability and robustness.
