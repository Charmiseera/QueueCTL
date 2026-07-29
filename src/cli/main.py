import sys
import os
# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import json
import argparse
import signal
import subprocess
import time
from src.services.queue_service import enqueue_job, list_jobs, retry_dlq_job, set_config, get_queue_status
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

def handle_config(args):
    try:
        if args.subcommand == "set":
            set_config(args.key, args.value)
            print(f"Configuration key '{args.key}' set to '{args.value}'.")
    except ValueError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(2)

def handle_status(args):
    try:
        status = get_queue_status()
        print("=== QueueCTL Status ===")
        print("\nJob State Counts:")
        states = ["pending", "processing", "completed", "failed", "dead"]
        for s in states:
            count = status["jobs"].get(s, 0)
            print(f"  {s.capitalize()}: {count}")
            
        print("\nActive Workers:")
        if not status["workers"]:
            print("  No active workers.")
        for w in status["workers"]:
            print(f"  ID: {w['id']} | PID: {w['pid']} | Last Heartbeat: {w['last_heartbeat']}")
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
    
    count = getattr(args, "count", 1) or 1
    
    if count > 1:
        processes = []
        print(f"Starting {count} parallel worker processes in foreground...", file=sys.stderr)
        try:
            for _ in range(count):
                p = subprocess.Popen([sys.executable, __file__, "worker", "start", "--count", "1"])
                processes.append(p)
            
            # Wait for all processes to finish, periodically checking if master received stop signal
            while processes and not worker_service.stop_requested:
                for p in list(processes):
                    ret = p.poll()
                    if ret is not None:
                        processes.remove(p)
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            if processes:
                print("Stopping all child worker processes...", file=sys.stderr)
                # Signal stop in DB so workers terminate gracefully
                with get_connection() as conn:
                    conn.execute("UPDATE workers SET should_stop = 1;")
                    conn.commit()
                # Wait for them to exit
                for p in processes:
                    try:
                        p.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        p.terminate()
    else:
        worker_service.worker_loop()

def handle_worker_stop(args):
    init_db()
    with get_connection() as conn:
        conn.execute("UPDATE workers SET should_stop = 1;")
        conn.commit()
    print("Sent stop signal to all active workers.")

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
            handle_worker_stop(args)
    elif args.command == "status":
        handle_status(args)
    elif args.command == "dlq":
        handle_dlq(args)
    elif args.command == "config":
        handle_config(args)

if __name__ == "__main__":
    main()
