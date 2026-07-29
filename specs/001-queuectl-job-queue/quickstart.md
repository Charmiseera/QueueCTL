# Quickstart & Validation Guide: QueueCTL Job Queue

This guide describes how to run and verify the five core validation scenarios for QueueCTL.

## Setup Prerequisites
Ensure you have Python 3.11+ installed. The database is stored locally inside the project root as `queuectl.db`.

```bash
# Verify python installation
python --version
```

---

## Scenario 1: A Basic Job Completes

### Actions
1. Enqueue a job that exits successfully (exit code 0).
2. Start the worker to process the job.
3. Check the final job status.

### Validation Commands
```bash
# 1. Enqueue the job
python src/cli/main.py enqueue '{"id":"job-success-1","command":"echo Hello"}'

# 2. Check pending status
python src/cli/main.py list --state pending --json

# 3. Start worker (runs in foreground, exit with Ctrl+C after it prints completion)
python src/cli/main.py worker start

# 4. Verify job is completed
python src/cli/main.py list --state completed --json
```

### Expected Output
- `list --state pending --json` displays `job-success-1`.
- Worker stdout displays execution logs showing `echo Hello` command returning exit code 0.
- `list --state completed --json` contains the completed job details.

---

## Scenario 2: A Failing Job Retries with Backoff and Lands in the DLQ

### Actions
1. Enqueue a job that fails (non-zero exit code).
2. Start the worker.
3. Observe retries with exponential delays.
4. Verify the job transitions to the DLQ state (`dead`).

### Validation Commands
```bash
# 1. Set configuration for fast testing
python src/cli/main.py config set max-retries 2
python src/cli/main.py config set backoff-base 2

# 2. Enqueue failing job (exits with code 1)
python src/cli/main.py enqueue '{"id":"job-fail-1","command":"python -c \"import sys; sys.exit(1)\""}'

# 3. Start worker
python src/cli/main.py worker start
```

### Expected Output
- Worker runs the job immediately, fails, and schedules a retry in $2^0 = 1$ second.
- Worker retries, fails, and schedules a retry in $2^1 = 2$ seconds.
- Worker retries, fails, reaches retry limit, and moves the job to the Dead Letter Queue.
- Running `python src/cli/main.py dlq list` displays `job-fail-1` in `dead` state.

---

## Scenario 3: Many Jobs across Multiple Workers (No Duplicates)

### Actions
1. Enqueue 20 jobs.
2. Launch 3 parallel workers from different terminal windows.
3. Verify all jobs complete and none are duplicated.

### Validation Commands
```bash
# 1. Enqueue 20 jobs (run scripts/enqueue_multi.py or run command manually)
# (Use terminal 1 to enqueue)
python -c "
import subprocess, json
for i in range(20):
    cmd = json.dumps({'id': f'job-concur-{i}', 'command': 'sleep 1'})
    subprocess.run(['python', 'src/cli/main.py', 'enqueue', cmd])
"

# 2. Run workers in separate terminals:
# Terminal 2:
python src/cli/main.py worker start
# Terminal 3:
python src/cli/main.py worker start
# Terminal 4:
python src/cli/main.py worker start

# 3. Check status from Terminal 1
python src/cli/main.py status
```

### Expected Output
- Workers run simultaneously, claiming and processing jobs concurrently.
- Each job is claimed by exactly one worker.
- At the end, `python src/cli/main.py list --state completed --json` lists exactly 20 completed jobs.

---

## Scenario 4: Worker SIGKILL mid-job Recovery

### Actions
1. Enqueue a long-running job.
2. Start a worker.
3. Abruptly kill the worker process using `SIGKILL` or Task Manager.
4. Run recovery check and verify the job is rescheduled.

### Validation Commands
```bash
# 1. Enqueue a 30s sleep job
python src/cli/main.py enqueue '{"id":"job-crash-1","command":"sleep 30"}'

# 2. Start worker
python src/cli/main.py worker start

# 3. Get the PID of the worker process and kill it (Terminal 2)
# Under Windows PowerShell:
Stop-Process -Name "python" -Force # Or kill the specific python worker PID

# 4. Wait 15 seconds. Run status to trigger/view recovery:
python src/cli/main.py status
```

### Expected Output
- The status command or next worker startup detects the worker check-in timeout (> 15 seconds).
- The job `job-crash-1` is reverted back to `pending`.
- A newly started worker picks up `job-crash-1` and executes it to completion.

---

## Scenario 5: Configuration Persistence & Retries Reset

### Actions
1. Configure `max-retries` and `backoff-base`.
2. Move a job to the DLQ.
3. Trigger a retry and verify the attempts reset.

### Validation Commands
```bash
# 1. Update config
python src/cli/main.py config set max-retries 3

# 2. Enqueue failing job and exhaust retries to move it to DLQ
python src/cli/main.py enqueue '{"id":"job-dlq-reset","command":"exit 1"}'
python src/cli/main.py worker start # Wait for it to hit DLQ

# 3. Trigger DLQ retry
python src/cli/main.py dlq retry job-dlq-reset

# 4. View job attempts counter (should be 0 and pending)
python src/cli/main.py list --state pending --json
```

### Expected Output
- The `list` output shows `job-dlq-reset` in state `pending` with `attempts` set back to `0`.
