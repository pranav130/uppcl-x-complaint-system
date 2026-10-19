"""Web service entrypoint for 24/7 cloud deployment (Render, Railway, Fly.io, etc.).

Runs a lightweight HTTP server on the port specified by $PORT (Render default: 10000)
while continuously executing the UPPCL complaint synchronization cycle in a background thread.
Provides an interactive visual web dashboard at / and JSON endpoints at /health and /sync.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from uppcl_x_automation.config import load_config
from uppcl_x_automation.orchestrator import UPPCLOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("uppcl_x_automation.server")

# Global state
CONFIG = load_config()
ORCHESTRATOR = UPPCLOrchestrator(CONFIG)
START_TIME = datetime.now(timezone.utc)
LAST_SYNC_TIME: Optional[datetime] = None
LAST_SYNC_SUMMARY: Optional[dict] = None
SYNC_LOCK = threading.Lock()


def run_cycle_safe() -> dict:
    """Run one synchronization cycle with thread lock protection."""
    global LAST_SYNC_TIME, LAST_SYNC_SUMMARY
    if not SYNC_LOCK.acquire(blocking=False):
        return {"status": "busy", "message": "A synchronization cycle is already running."}
    try:
        summary = ORCHESTRATOR.run_sync_cycle()
        LAST_SYNC_TIME = datetime.now(timezone.utc)
        LAST_SYNC_SUMMARY = {
            "timestamp": LAST_SYNC_TIME.isoformat(),
            "posts_fetched": summary.posts_fetched,
            "duplicates_skipped": summary.duplicates_skipped,
            "complaints_classified": summary.complaints_classified,
            "appreciations_logged": summary.appreciation_count,
            "rows_appended": summary.rows_appended,
            "highest_post_id": summary.highest_post_id,
            "errors": summary.errors,
        }
        return {"status": "success", "summary": LAST_SYNC_SUMMARY}
    except Exception as e:
        logger.exception("Error during sync cycle: %s", e)
        return {"status": "error", "error": str(e)}
    finally:
        SYNC_LOCK.release()


def background_worker(interval_minutes: int):
    """Background daemon loop that triggers sync every interval_minutes."""
    interval_seconds = interval_minutes * 60
    logger.info("Background worker started. Interval: %d minutes (%d seconds).", interval_minutes, interval_seconds)
    time.sleep(10)
    while True:
        try:
            logger.info("Background worker triggering scheduled sync cycle...")
            run_cycle_safe()
        except Exception as e:
            logger.exception("Unexpected error in background worker loop: %s", e)
        time.sleep(interval_seconds)


def render_html_dashboard(stats: dict, uptime_human: str) -> str:
    """Render a modern visual dashboard for the UPPCL complaint system."""
    discom_items = stats.get("discom_breakdown", {})
    last_sync = LAST_SYNC_TIME.strftime("%Y-%m-%d %H:%M:%S UTC") if LAST_SYNC_TIME else "Initializing..."
    rows_appended = LAST_SYNC_SUMMARY.get("rows_appended", 0) if LAST_SYNC_SUMMARY else 0
    sheet_url = f"https://docs.google.com/spreadsheets/d/{CONFIG.google_spreadsheet_id}/edit"

    discom_cards = ""
    for d, count in discom_items.items():
        discom_cards += f"""
        <div class="card stat-sub">
          <div class="stat-name">{d}</div>
          <div class="stat-num">{count}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UPPCL X Grievance Monitor - 24/7 Cloud Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: #0284c7;
      --primary-dark: #0369a1;
      --bg: #0b1120;
      --surface: #1e293b;
      --surface-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --success: #10b981;
      --warning: #f59e0b;
      --cyan: #4dd0e1;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 24px;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--surface-border);
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .title-group h1 {{ font-size: 24px; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 10px; }}
    .title-group p {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
    .status-badge {{
      background: rgba(16, 185, 129, 0.15);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 8px 16px;
      border-radius: 9999px;
      font-weight: 700;
      font-size: 13px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .pulse {{ width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 10px var(--success); }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 12px;
      padding: 20px;
    }}
    .card-label {{ color: var(--text-muted); font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
    .card-value {{ font-size: 32px; font-weight: 800; margin-top: 8px; color: #fff; font-family: 'JetBrains Mono', monospace; }}
    .card-sub {{ font-size: 12px; color: var(--text-muted); margin-top: 6px; }}
    .discom-section {{ margin-bottom: 24px; }}
    .section-title {{ font-size: 16px; font-weight: 700; margin-bottom: 12px; color: var(--cyan); }}
    .discom-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }}
    .stat-sub {{ padding: 14px; text-align: center; }}
    .stat-name {{ font-weight: 700; font-size: 14px; color: #cbd5e1; }}
    .stat-num {{ font-size: 24px; font-weight: 800; color: var(--cyan); margin-top: 4px; font-family: 'JetBrains Mono', monospace; }}
    .actions-bar {{
      display: flex;
      gap: 12px;
      margin-top: 24px;
      flex-wrap: wrap;
    }}
    .btn {{
      padding: 12px 20px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 14px;
      text-decoration: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: none;
      transition: all 0.2s;
    }}
    .btn-primary {{ background: var(--primary); color: white; }}
    .btn-primary:hover {{ background: var(--primary-dark); }}
    .btn-outline {{ background: transparent; color: #fff; border: 1px solid var(--surface-border); }}
    .btn-outline:hover {{ background: var(--surface); }}
    .footer {{ margin-top: 40px; text-align: center; color: var(--text-muted); font-size: 13px; border-top: 1px solid var(--surface-border); padding-top: 20px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>⚡ UPPCL X Grievance Monitor</h1>
        <p>24/7 Autonomous Cloud Daemon · Running on Render</p>
      </div>
      <div class="status-badge">
        <span class="pulse"></span> 24/7 CLOUD ACTIVE
      </div>
    </header>

    <div class="grid-4">
      <div class="card">
        <div class="card-label">Total Detected Posts</div>
        <div class="card-value">{stats.get('total_detected', 0)}</div>
        <div class="card-sub">{stats.get('today_detected', 0)} detected today</div>
      </div>
      <div class="card">
        <div class="card-label">Last Appended Batch</div>
        <div class="card-value" style="color: var(--success);">{rows_appended}</div>
        <div class="card-sub">Rows synchronized to Google Sheet</div>
      </div>
      <div class="card">
        <div class="card-label">Polling Interval</div>
        <div class="card-value">{CONFIG.polling_interval_minutes}m</div>
        <div class="card-sub">Auto-syncs every 5 minutes</div>
      </div>
      <div class="card">
        <div class="card-label">System Uptime</div>
        <div class="card-value" style="font-size: 22px; padding-top: 8px;">{uptime_human}</div>
        <div class="card-sub">Last sync: {last_sync}</div>
      </div>
    </div>

    <div class="discom-section">
      <div class="section-title">Distribution by Power Distribution Corporation (DISCOM)</div>
      <div class="discom-grid">
        {discom_cards}
      </div>
    </div>

    <div class="actions-bar">
      <a href="{sheet_url}" target="_blank" class="btn btn-primary">
        📊 Open Google Spreadsheet
      </a>
      <button onclick="triggerSync()" id="syncBtn" class="btn btn-outline">
        ⚡ Trigger Sync Now
      </button>
      <a href="/status" target="_blank" class="btn btn-outline">
        Inspect JSON Status
      </a>
    </div>

    <div id="syncResult" style="margin-top: 16px; font-size: 14px; color: var(--cyan);"></div>

    <div class="footer">
      UPPCL Social Media Cell & Grievance Automation System · Independent 24/7 Cloud Worker
    </div>
  </div>

  <script>
    async function triggerSync() {{
      const btn = document.getElementById('syncBtn');
      const resDiv = document.getElementById('syncResult');
      btn.innerText = 'Syncing...';
      btn.disabled = true;
      resDiv.innerText = 'Triggering cloud sync cycle on Render...';
      try {{
        const res = await fetch('/sync', {{ method: 'POST' }});
        const data = await res.json();
        resDiv.innerText = 'Sync complete! ' + (data.summary ? data.summary.rows_appended + ' new rows appended.' : data.message || 'Done');
        setTimeout(() => {{ window.location.reload(); }}, 2000);
      }} catch (e) {{
        resDiv.innerText = 'Error triggering sync: ' + e;
      }} finally {{
        btn.innerText = '⚡ Trigger Sync Now';
        btn.disabled = false;
      }}
    }}
    // Auto refresh every 30 seconds to show live counts
    setTimeout(() => {{ window.location.reload(); }}, 30000);
  </script>
</body>
</html>
"""


class UPPCLRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks and status queries."""

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        accept_header = self.headers.get("Accept", "")

        if self.path in ("/", "/dashboard"):
            if "application/json" in accept_header and "text/html" not in accept_header:
                self.send_json_status()
            else:
                self.send_html_dashboard()

        elif self.path in ("/health", "/status", "/api/status"):
            self.send_json_status()

        elif self.path in ("/sync", "/trigger"):
            logger.info("Manual sync triggered via HTTP endpoint %s", self.path)
            res = run_cycle_safe()
            code = 200 if res.get("status") in ("success", "busy") else 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode("utf-8"))

    def send_html_dashboard(self):
        stats = ORCHESTRATOR.checkpoint.get_summary_stats()
        uptime_seconds = int((datetime.now(timezone.utc) - START_TIME).total_seconds())
        uptime_human = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
        html = render_html_dashboard(stats, uptime_human)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def send_json_status(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        stats = ORCHESTRATOR.checkpoint.get_summary_stats()
        uptime_seconds = int((datetime.now(timezone.utc) - START_TIME).total_seconds())

        payload = {
            "service": "UPPCL X Complaint Monitoring 24/7 Cloud Service",
            "status": "healthy",
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
            "polling_interval_minutes": CONFIG.polling_interval_minutes,
            "dry_run": CONFIG.dry_run,
            "last_sync_time": LAST_SYNC_TIME.isoformat() if LAST_SYNC_TIME else None,
            "last_sync_summary": LAST_SYNC_SUMMARY,
            "database_stats": stats,
        }
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def do_POST(self):
        if self.path in ("/sync", "/trigger"):
            self.do_GET()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))


def main():
    port = int(os.environ.get("PORT", "10000"))
    host = "0.0.0.0"

    logger.info("Starting UPPCL 24/7 Cloud Service on %s:%d...", host, port)

    # Start background synchronization worker thread
    worker_thread = threading.Thread(
        target=background_worker,
        args=(CONFIG.polling_interval_minutes,),
        daemon=True,
    )
    worker_thread.start()

    server = HTTPServer((host, port), UPPCLRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
