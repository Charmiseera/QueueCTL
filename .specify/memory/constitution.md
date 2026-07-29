<!--
SYNC IMPACT REPORT
- Version change: None -> 1.0.0
- List of modified principles:
  * [PRINCIPLE_1_NAME] -> I. CLI-First Interface
  * [PRINCIPLE_2_NAME] -> II. Crash Recovery & Resilience
  * [PRINCIPLE_3_NAME] -> III. Process-Safe Concurrency
  * [PRINCIPLE_4_NAME] -> IV. Retry & Dead Letter Queue (DLQ)
  * [PRINCIPLE_5_NAME] -> V. Traceability & Defensive Documentation
- Added sections:
  * Architectural & Implementation Constraints
  * Submission & Validation Standards
- Removed sections: None
- Templates requiring updates:
  * .specify/templates/plan-template.md (✅ updated)
- Follow-up TODOs: None
-->

# QueueCTL Constitution

## Core Principles

### I. CLI-First Interface
All user and automated interactions with QueueCTL MUST occur through the CLI command interface. The system must implement the exact command syntax, signal behavior, and output schema specified in the project requirements. Specifically, `queuectl list --state <state> --json` MUST output a JSON array of job objects and nothing else to stdout. Workers started via `worker start` must run in the foreground and handle SIGTERM/SIGINT (Ctrl+C) gracefully by finishing the active job before exiting. Cross-process signalling commands (e.g. `worker stop`) must function reliably from separate terminals.

### II. Crash Recovery & Resilience
A job must never be stuck in `processing` if a worker process dies (e.g., due to SIGKILL or system crash). The system MUST actively detect worker crashes and recover affected jobs so they can be re-executed. Under default configurations, the worst-case recovery latency must be strictly less than 60 seconds to satisfy the requirements of the automated validation suite.

### III. Process-Safe Concurrency
Multiple workers MUST be able to execute jobs in parallel, including workers launched as separate OS processes from different terminal sessions. Claiming a job must be atomic across separate processes: no job may ever be claimed or executed by more than one worker at a time. The atomic claiming mechanism must be explicitly identified and defended.

### IV. Retry & Dead Letter Queue (DLQ)
Failed jobs must retry automatically with exponential backoff delay calculated as `delay = base ^ attempts` seconds. The retry base must be configurable via `queuectl config set backoff-base`. Upon exhausting `max_retries`, the job must be transitioned to the Dead Letter Queue (`dead`). Dead jobs can be retried using `dlq retry <id>`, and the system must explicitly define and justify whether this operation resets the attempts counter.

### V. Traceability & Defensive Documentation
Every architectural decision, trade-off, and implementation choice must be documented in `DECISIONS.md`. In particular, the five required questions (covering concurrency atomicity, crash recovery steps/latencies, DLQ retry attempt reset logic, cross-process signaling, and priority queue extensibility) must be fully answered. Git commit history must show clear, incremental progress. The author must be capable of explaining and modifying any part of the codebase during the live review.

## Architectural & Implementation Constraints
QueueCTL must support persistent job storage that survives process restarts and crashes (such as file-based JSON, SQLite, or equivalent). The storage implementation must support the process-level locking required for concurrency safety. Configuration settings must also be persisted.

## Submission & Validation Standards
All submissions must pass the five core validation scenarios (basic completion, retry/backoff, multi-worker parallel execution, SIGKILL mid-job survival, and full restart persistence) before delivery. The implementation must strictly adhere to the signaling contracts and CLI return formats to ensure automated test scripts do not fail due to interface mismatches.

## Governance
This constitution serves as the ultimate source of truth for QueueCTL design and implementation. Any modifications or extensions to the CLI interface or concurrency requirements require amending this constitution and incrementing the version. The constitution compliance must be verified at every implementation phase.

**Version**: 1.0.0 | **Ratified**: 2026-07-29 | **Last Amended**: 2026-07-29
