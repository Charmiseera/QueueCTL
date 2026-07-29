import http.server
import socketserver
import json
import urllib.parse
import sys
import os
from datetime import datetime

# Add project root to sys.path if direct run
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.db_service import get_connection, init_db
from src.services.queue_service import enqueue_job, list_jobs, get_queue_status

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QueueCTL Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(51, 65, 85, 0.5);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-primary: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.15);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --processing: #3b82f6;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.1) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.05) 0px, transparent 50%);
            background-attachment: fixed;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }

        .logo {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #818cf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .badge-live {
            background-color: rgba(16, 185, 129, 0.15);
            color: var(--success);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            border: 1px solid rgba(16, 185, 129, 0.25);
        }

        .badge-live::before {
            content: '';
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        .metric-card:hover {
            transform: translateY(-4px);
            border-color: rgba(99, 102, 241, 0.4);
            box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.1);
        }

        .metric-title {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }

        .metric-value {
            font-size: 2.25rem;
            font-weight: 700;
        }

        .main-layout {
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 2rem;
            align-items: start;
        }

        .control-panel {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .glass-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.75rem;
        }

        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .form-group {
            margin-bottom: 1.25rem;
        }

        .form-label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .form-input {
            width: 100%;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            color: var(--text-primary);
            font-size: 0.95rem;
            transition: border-color 0.2s;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }

        .btn {
            display: inline-flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            padding: 0.75rem 1.25rem;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
            text-align: center;
        }

        .btn-primary {
            background: var(--accent-primary);
            color: white;
        }

        .btn-primary:hover {
            background: #4f46e5;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.45);
        }

        .btn-danger {
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .btn-danger:hover {
            background: var(--danger);
            color: white;
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.45);
        }

        .worker-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .worker-item:last-child {
            border-bottom: none;
        }

        .worker-id {
            font-weight: 600;
            font-size: 0.9rem;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .worker-pid {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        .job-table-container {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            padding: 1rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 1rem;
            font-size: 0.95rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            vertical-align: middle;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .badge-state {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-pending { background: rgba(148, 163, 184, 0.15); color: var(--text-secondary); }
        .badge-processing { background: rgba(59, 130, 246, 0.15); color: var(--processing); }
        .badge-completed { background: rgba(16, 185, 129, 0.15); color: var(--success); }
        .badge-failed { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
        .badge-dead { background: rgba(239, 68, 68, 0.15); color: var(--danger); }

        .btn-log {
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-radius: 0.25rem;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-log:hover {
            background: var(--accent-primary);
            border-color: var(--accent-primary);
        }

        /* Modal styling */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(8px);
            z-index: 100;
            justify-content: center;
            align-items: center;
        }

        .modal-content {
            background: #1e293b;
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            width: 90%;
            max-width: 650px;
            padding: 2rem;
            position: relative;
        }

        .modal-close {
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.5rem;
            cursor: pointer;
            color: var(--text-secondary);
        }

        .modal-close:hover {
            color: white;
        }

        .log-section {
            margin-top: 1.25rem;
        }

        .log-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }

        .log-box {
            background: #090d16;
            padding: 1rem;
            border-radius: 0.5rem;
            font-family: monospace;
            font-size: 0.85rem;
            max-height: 200px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: var(--success);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 0.5rem;
            font-weight: 600;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
            transform: translateY(150%);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 200;
        }

        .toast.show {
            transform: translateY(0);
        }
    </style>
</head>
<body>

    <header>
        <div class="logo">QueueCTL Dashboard</div>
        <div class="badge-live">LIVE MONITORING</div>
    </header>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-title">Pending Jobs</div>
            <div class="metric-value" id="metric-pending">-</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Processing Jobs</div>
            <div class="metric-value" style="color: var(--processing);" id="metric-processing">-</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Completed Jobs</div>
            <div class="metric-value" style="color: var(--success);" id="metric-completed">-</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Failed / Dead</div>
            <div class="metric-value" style="color: var(--danger);" id="metric-failed-dead">-</div>
        </div>
    </div>

    <div class="main-layout">
        <div class="control-panel">
            <div class="glass-card">
                <div class="card-title">Enqueue Job</div>
                <form id="enqueue-form">
                    <div class="form-group">
                        <label class="form-label">Job ID</label>
                        <input type="text" class="form-input" id="job-id" placeholder="job-100" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Shell Command</label>
                        <input type="text" class="form-input" id="job-command" placeholder="echo 'Hello'" required>
                    </div>
                    <div class="form-group" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div>
                            <label class="form-label">Priority</label>
                            <input type="number" class="form-input" id="job-priority" value="0">
                        </div>
                        <div>
                            <label class="form-label">Timeout (s)</label>
                            <input type="number" class="form-input" id="job-timeout" value="60">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Enqueue Job</button>
                </form>
            </div>

            <div class="glass-card">
                <div class="card-title">Active Workers</div>
                <div id="workers-list">
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">Loading workers...</p>
                </div>
                <button onclick="stopAllWorkers()" class="btn btn-danger" style="margin-top: 1.25rem;">Signal Stop All</button>
            </div>
        </div>

        <div class="glass-card" style="align-self: stretch;">
            <div class="card-title">All Jobs</div>
            <div class="job-table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Job ID</th>
                            <th>Command</th>
                            <th>State</th>
                            <th>Attempts</th>
                            <th>Priority</th>
                            <th>Timeout</th>
                            <th>Logs</th>
                        </tr>
                    </thead>
                    <tbody id="jobs-tbody">
                        <tr>
                            <td colspan="7" style="text-align: center; color: var(--text-secondary);">Loading jobs...</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="log-modal" class="modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeLogs()">&times;</span>
            <h2 id="log-modal-title">Job Log View</h2>
            <div class="log-section">
                <div class="log-title">Standard Output (stdout)</div>
                <div class="log-box" id="log-stdout">None</div>
            </div>
            <div class="log-section">
                <div class="log-title">Standard Error (stderr)</div>
                <div class="log-box" id="log-stderr" style="color: var(--danger);">None</div>
            </div>
        </div>
    </div>

    <div id="toast" class="toast">Job enqueued successfully!</div>

    <script>
        let allJobs = [];

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // Update metrics
                document.getElementById('metric-pending').innerText = data.jobs.pending || 0;
                document.getElementById('metric-processing').innerText = data.jobs.processing || 0;
                document.getElementById('metric-completed').innerText = data.jobs.completed || 0;
                document.getElementById('metric-failed-dead').innerText = (data.jobs.failed || 0) + (data.jobs.dead || 0);

                // Update workers
                const workersList = document.getElementById('workers-list');
                if (data.workers.length === 0) {
                    workersList.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No active workers.</p>';
                } else {
                    workersList.innerHTML = data.workers.map(w => `
                        <div class="worker-item">
                            <div>
                                <div class="worker-id" title="${w.id}">${w.id}</div>
                                <div class="worker-pid">PID: ${w.pid}</div>
                            </div>
                            <div style="font-size: 0.75rem; color: var(--success); font-weight: 600;">ACTIVE</div>
                        </div>
                    `).join('');
                }

                // Update jobs table
                allJobs = data.all_jobs;
                const tbody = document.getElementById('jobs-tbody');
                if (data.all_jobs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No jobs in queue.</td></tr>';
                } else {
                    tbody.innerHTML = data.all_jobs.map(j => `
                        <tr>
                            <td style="font-weight: 600;">${escapeHtml(j.id)}</td>
                            <td style="font-family: monospace; font-size: 0.85rem; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(j.command)}</td>
                            <td><span class="badge-state badge-${j.state}">${j.state}</span></td>
                            <td>${j.attempts}/${j.max_retries}</td>
                            <td>${j.priority || 0}</td>
                            <td>${j.timeout || 60}s</td>
                            <td><button onclick="viewLogs('${j.id}')" class="btn-log">Logs</button></td>
                        </tr>
                    `).join('');
                }
            } catch (err) {
                console.error("Error fetching status:", err);
            }
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
        }

        function viewLogs(jobId) {
            const job = allJobs.find(j => j.id === jobId);
            if (!job) return;

            document.getElementById('log-modal-title').innerText = `Logs for ${jobId}`;
            document.getElementById('log-stdout').innerText = job.stdout || 'No stdout recorded.';
            document.getElementById('log-stderr').innerText = job.stderr || 'No stderr recorded.';
            document.getElementById('log-modal').style.display = 'flex';
        }

        function closeLogs() {
            document.getElementById('log-modal').style.display = 'none';
        }

        async function stopAllWorkers() {
            if (!confirm("Are you sure you want to signal all workers to stop?")) return;
            try {
                const res = await fetch('/api/stop', { method: 'POST' });
                if (res.ok) {
                    showToast("Stop signal sent to all workers.");
                    fetchStatus();
                }
            } catch (err) {
                console.error(err);
            }
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.innerText = msg;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        // Form submit
        document.getElementById('enqueue-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('job-id').value.trim();
            const command = document.getElementById('job-command').value.trim();
            const priority = parseInt(document.getElementById('job-priority').value) || 0;
            const timeout = parseInt(document.getElementById('job-timeout').value) || 60;

            try {
                const res = await fetch('/api/enqueue', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id, command, priority, timeout })
                });

                if (res.ok) {
                    showToast(`Job ${id} enqueued!`);
                    document.getElementById('job-id').value = '';
                    document.getElementById('job-command').value = '';
                    fetchStatus();
                } else {
                    const errText = await res.text();
                    alert(`Failed to enqueue: ${errText}`);
                }
            } catch (err) {
                console.error(err);
            }
        });

        // Initialize and poll
        fetchStatus();
        setInterval(fetchStatus, 3000);
    </script>
</body>
</html>
"""

class DashboardHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to stdout/stderr so as not to clutter the worker/dashboard CLI logs
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            # Fetch status
            status = get_queue_status()
            # Fetch all jobs to show in UI
            all_jobs = list_jobs()
            status["all_jobs"] = [j.to_dict() for j in all_jobs]
            
            self.wfile.write(json.dumps(status).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/enqueue":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                job_id = data.get("id")
                command = data.get("command")
                priority = data.get("priority", 0)
                timeout = data.get("timeout", 60)
                
                if not job_id or not command:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"id and command are required.")
                    return
                
                enqueue_job(job_id, command, priority=priority, timeout=timeout)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
                
        elif self.path == "/api/stop":
            try:
                init_db()
                with get_connection() as conn:
                    conn.execute("UPDATE workers SET should_stop = 1;")
                    conn.commit()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Stop signal sent.")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def start_dashboard_server(port=8085):
    """Starts the dashboard HTTP server."""
    handler = DashboardHTTPRequestHandler
    # Allow address reuse to avoid port binding errors during quick restarts
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"=== QueueCTL Web Dashboard running on http://localhost:{port} ===")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Dashboard server gracefully...")
            httpd.server_close()

if __name__ == "__main__":
    start_dashboard_server()
