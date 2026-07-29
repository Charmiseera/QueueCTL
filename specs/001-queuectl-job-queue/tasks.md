# Tasks: QueueCTL Job Queue

**Input**: Design documents from `specs/001-queuectl-job-queue/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks are included to verify functionality against assignment requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths shown below assume single project structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directories `src/cli/`, `src/models/`, `src/services/`, `tests/unit/`, `tests/integration/`, `tests/contract/` per implementation plan
- [x] T002 Initialize configuration paths and database name constants in `src/config.py`
- [x] T003 [P] Create initial test suite helper packages and `__init__.py` files in `tests/` directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Implement SQLite schema creation and connection helper in `src/services/db_service.py`
- [x] T005 [P] Implement job entity model representation class in `src/models/job.py`
- [x] T006 [P] Implement worker entity model representation class in `src/models/worker.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Job Enqueue & Execution (Priority: P1) 🎯 MVP

**Goal**: Support submitting jobs via CLI and executing them inside a worker process.

**Independent Test**: Enqueue a job, start worker, check stdout and job status.

### Tests for User Story 1

- [x] T007 [P] [US1] Create unit tests for Job serialization and state queries in `tests/unit/test_models.py`
- [x] T008 [P] [US1] Create contract test for `enqueue` and `list` output format in `tests/contract/test_cli.py`

### Implementation for User Story 1

- [x] T009 [US1] Implement enqueuing database operations and queue listings in `src/services/queue_service.py`
- [x] T010 [US1] Implement basic job execution using subprocess command runners in `src/services/worker_service.py`
- [x] T011 [US1] Create command routing parser for `enqueue` and `list` in `src/cli/main.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Automatic Retries & DLQ (Priority: P1)

**Goal**: Automatically retry failed executions using exponential backoff and isolate permanently failed jobs into the DLQ state.

**Independent Test**: Enqueue a failing job, verify worker fails, waits, retries up to max_retries, and transitions it to `dead`. Verify retrying resets attempts.

### Tests for User Story 2

- [x] T012 [P] [US2] Create unit tests for exponential backoff calculations in `tests/unit/test_models.py`

### Implementation for User Story 2

- [x] T013 [US2] Implement exponential backoff delay calculation logic (`delay = base ^ attempts` seconds) in `src/models/job.py`
- [x] T014 [US2] Implement retry scheduler and DLQ transition database updates in `src/services/queue_service.py`
- [x] T015 [US2] Implement `dlq list` and `dlq retry` commands in `src/cli/main.py`
- [x] T016 [US2] Implement retry execution checks in the worker loop in `src/services/worker_service.py`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Concurrent Multi-Worker Execution (Priority: P1)

**Goal**: Safely run multiple worker processes in parallel from separate terminal sessions without executing any job twice.

**Independent Test**: Run multiple concurrent workers and verify no duplicate claims occur.

### Tests for User Story 3

- [x] T017 [P] [US3] Create concurrency integration tests in `tests/integration/test_queue.py` simulating parallel workers

### Implementation for User Story 3

- [x] T018 [US3] Implement atomic job claim transaction utilizing `BEGIN IMMEDIATE` in `src/services/db_service.py`
- [x] T019 [US3] Implement worker selection logic in `src/services/worker_service.py` using the atomic claim transaction
- [x] T020 [US3] Implement `worker start` and `worker stop` CLI commands in `src/cli/main.py`

**Checkpoint**: At this point, User Stories 1, 2, and 3 should work concurrently

---

## Phase 6: User Story 4 - Crash Recovery & SIGKILL Resilience (Priority: P1)

**Goal**: Automatically detect worker crash/SIGKILL and recover orphaned jobs back to `pending` in under 60 seconds.

**Independent Test**: Start worker mid-job, SIGKILL, run recovery check, and verify job is reset.

### Tests for User Story 4

- [x] T021 [P] [US4] Create crash recovery integration test in `tests/integration/test_queue.py` verifying recovery triggers under 60 seconds

### Implementation for User Story 4

- [x] T022 [US4] Implement worker registration and heartbeat check-in in `src/services/worker_service.py`
- [x] T023 [US4] Implement orphan search query and recovery update in `src/services/queue_service.py`
- [x] T024 [US4] Implement periodic heartbeat update loop in worker execution thread/process in `src/services/worker_service.py`

---

## Phase 7: User Story 5 - CLI Configuration Management (Priority: P2)

**Goal**: View and modify key parameters dynamically via CLI and ensure persistence.

**Independent Test**: Modify `max-retries` and verify it applies to new jobs.

### Tests for User Story 5

- [x] T025 [P] [US5] Create unit tests in `tests/unit/test_services.py` for config getter and setter overrides

### Implementation for User Story 5

- [x] T026 [US5] Implement get/set operations in `src/services/queue_service.py` for persistent configuration keys (`max-retries` and `backoff-base`)
- [x] T027 [US5] Implement `config set` parsing in `src/cli/main.py`

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T028 Add README.md with setup, usage, and architecture overview
- [ ] T029 Complete DECISIONS.md answering the 5 mandatory design questions
- [ ] T030 Verify and run the entire test suite to ensure all scenario validations pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "T007 [P] [US1] Create unit tests for Job serialization and state queries in tests/unit/test_models.py"
Task: "T008 [P] [US1] Create contract test for enqueue and list output format in tests/contract/test_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories
