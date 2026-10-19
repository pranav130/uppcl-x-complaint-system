"""Web service entrypoint for 24/7 cloud deployment (Render, Railway, Fly.io, etc.).

Runs a lightweight HTTP server on the port specified by $PORT (Render default: 10000)
while continuously executing the UPPCL complaint synchronization cycle in a background thread.
Does not require any additional third-party web frameworks (uses Python standard library).
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
    # Allow initial server spin-up before first poll
    time.sleep(10)
    while True:
        try:
            logger.info("Background worker triggering scheduled sync cycle...")
            run_cycle_safe()
        except Exception as e:
            logger.exception("Unexpected error in background worker loop: %s", e)
        time.sleep(interval_seconds)


class UPPCLRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks and status queries."""

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/health", "/status"):
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

    def do_POST(self):
        if self.path in ("/sync", "/trigger"):
            self.do_GET()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Override to log via standard logger instead of stderr
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
