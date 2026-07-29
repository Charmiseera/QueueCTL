import sys
import os
# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import json
import argparse
import signal
from src.services.queue_service import enqueue_job, list_jobs, retry_dlq_job
from src.services.db_service import init_db, get_connection
import src.services.worker_service as worker_service

def handle_enqueue(args):
    try:
        data = json.loads(args.json_data)
        job_id = data.get("id")
        command = data.get("command")
        max_retries = data.get("max_retries")
        
        if not job_id or not command:
            print("Error: JSON must contain 'id' and 'command'.", file=sys.stderr)
            sys.exit(1)
            
        enqueue_job(job_id, command, max_retries)
        print(f"Job {job_id} enqueued successfully.")
    except json.JSONDecodeError:
        print("Error: Invalid JSON string.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(2)

def handle_list(args):
    try:
        jobs = list_jobs(args.state)
        if args.json:
            # Strictly print ONLY the JSON array on stdout
            job_dicts = [job.to_dict() for job in jobs]
            print(json.dumps(job_dicts))
        else:
            if not jobs:
                print("No jobs found.")
            for job in jobs:
                print(f"ID: {job.id} | Command: {job.command} | State: {job.state} | Attempts: {job.attempts}/{job.max_retries}")
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(2)

def handle_dlq(args):
    try:
        if args.subcommand == "list":
            jobs = list_jobs("dead")
            # If they want JSON format, we could support that or default to print layout
            # Standard list command already handles --json, but we can do a simple print here:
            if not jobs:
                print("No jobs in DLQ.")
            for job in jobs:
                print(f"ID: {job.id} | Command: {job.command} | State: {job.state} | Attempts: {job.attempts}/{job.max_retries}")
        elif args.subcommand == "retry":
            retry_dlq_job(args.job_id)
            print(f"Job {args.job_id} successfully re-enqueued from DLQ.")
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(2)

def setup_signals():
    """Trap SIGINT (Ctrl+C) and SIGTERM to stop worker gracefully."""
    def signal_handler(sig, frame):
        print("\nGraceful shutdown signal received. Shutting down after current job completes...")
        worker_service.stop_requested = True
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def handle_worker_start(args):
    init_db()
    setup_signals()
    
    # Check count option
    count = getattr(args, "count", 1) or 1
    
    if count > 1:
        # We will implement multi-process start in US3
        print(f"Starting {count} worker processes in background (simulated in foreground master)...", file=sys.stderr)
        # For now, let's just run a single worker in the foreground for US1
        worker_service.worker_loop()
    else:
        worker_service.worker_loop()

def main():
    parser = argparse.ArgumentParser(description="QueueCTL CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # enqueue
    enqueue_parser = subparsers.add_parser("enqueue")
    enqueue_parser.add_argument("json_data", help="JSON data containing id and command")

    # list
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--state", required=True, choices=["pending", "processing", "completed", "failed", "dead"], help="Filter by job state")
    list_parser.add_argument("--json", action="store_true", help="Format output as JSON array")

    # worker subparsers
    worker_parser = subparsers.add_parser("worker")
    worker_subparsers = worker_parser.add_subparsers(dest="subcommand", required=True)
    
    # worker start
    worker_start_parser = worker_subparsers.add_parser("start")
    worker_start_parser.add_argument("--count", type=int, default=1, help="Number of concurrent workers")

    # worker stop
    worker_stop_parser = worker_subparsers.add_parser("stop")

    # status
    subparsers.add_parser("status")

    # dlq subparsers
    dlq_parser = subparsers.add_parser("dlq")
    dlq_subparsers = dlq_parser.add_subparsers(dest="subcommand", required=True)
    
    # dlq list
    dlq_subparsers.add_parser("list")
    
    # dlq retry
    dlq_retry_parser = dlq_subparsers.add_parser("retry")
    dlq_retry_parser.add_argument("job_id", help="Job ID to retry")

    # config subparsers
    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="subcommand", required=True)
    
    # config set
    config_set_parser = config_subparsers.add_parser("set")
    config_set_parser.add_argument("key", choices=["max-retries", "backoff-base"], help="Configuration key")
    config_set_parser.add_argument("value", help="Configuration value")

    args = parser.parse_args()

    if args.command == "enqueue":
        handle_enqueue(args)
    elif args.command == "list":
        handle_list(args)
    elif args.command == "worker":
        if args.subcommand == "start":
            handle_worker_start(args)
        elif args.subcommand == "stop":
            # Will implement under US3 / worker stop
            pass
    elif args.command == "status":
        # Will implement under status
        pass
    elif args.command == "dlq":
        handle_dlq(args)
    elif args.command == "config":
        # Will implement under config
        pass

if __name__ == "__main__":
    main()
