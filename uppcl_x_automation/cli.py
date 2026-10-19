"""Command Line Interface for UPPCL X Complaint Automation.

Provides commands to run synchronizations, dry-runs, health checks,
interactive routing tests, and system status queries.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

# Ensure UTF-8 output on Windows consoles for Hindi text
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from uppcl_x_automation.config import load_config
from uppcl_x_automation.orchestrator import UPPCLOrchestrator
from uppcl_x_automation.checkpoint import CheckpointStore
from uppcl_x_automation.router import DiscomRouter
from uppcl_x_automation.classifier import GrievanceClassifier


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_sync(args: argparse.Namespace) -> int:
    """Run synchronization cycles."""
    config = load_config(config_path=args.config, env_path=args.env)
    if args.dry_run:
        config.dry_run = True

    orchestrator = UPPCLOrchestrator(config)

    if getattr(args, "reset_watermark", False):
        orchestrator.checkpoint.clear_watermark()
        print("[*] Watermark cleared. Repolling all available posts...")

    if args.daemon:
        interval_sec = config.polling_interval_minutes * 60
        print(f"[*] Starting continuous monitoring daemon (Interval: {config.polling_interval_minutes}m, Dry-run: {config.dry_run}). Press Ctrl+C to stop.")
        try:
            while True:
                summary = orchestrator.run_sync_cycle()
                print(f"[+] Cycle completed: {summary.posts_fetched} fetched, {summary.complaints_classified} complaints, {summary.rows_appended} appended.")
                if summary.errors:
                    print(f"[!] Errors encountered: {summary.errors}")
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("\n[*] Monitoring stopped by user.")
            return 0
    else:
        print(f"[*] Running single synchronization cycle (Dry-run: {config.dry_run})...")
        summary = orchestrator.run_sync_cycle()
        print("\n" + "=" * 60)
        print("UPPCL SYNCHRONIZATION SUMMARY")
        print("=" * 60)
        print(f"Posts Fetched:           {summary.posts_fetched}")
        print(f"Duplicates Skipped:      {summary.duplicates_skipped}")
        print(f"Complaints Classified:   {summary.complaints_classified}")
        print(f"Appreciations Logged:    {summary.appreciation_count}")
        print(f"Non-complaints Skipped:  {summary.non_complaints_skipped}")
        print(f"Drafts Prepared:         {summary.drafts_prepared}")
        print(f"Replies Published:       {summary.replies_published}")
        print(f"Rows Appended:           {summary.rows_appended}")
        print(f"Watermark (Latest ID):   {summary.highest_post_id or 'N/A'}")
        if summary.errors:
            print(f"Errors ({len(summary.errors)}):")
            for err in summary.errors:
                print(f"  - {err}")
        print("=" * 60)
        return 0 if not summary.errors else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Display SQLite checkpoint status and metrics."""
    config = load_config(config_path=args.config, env_path=args.env)
    store = CheckpointStore(config.sqlite_db_path)
    stats = store.get_summary_stats()
    last_id = store.get_last_seen_post_id()

    print("\n" + "=" * 60)
    print("UPPCL COMPLAINT MONITOR STATUS & METRICS")
    print("=" * 60)
    print(f"Database Path:           {config.sqlite_db_path}")
    print(f"Total Detected Posts:    {stats['total_detected']}")
    print(f"Detected Today:          {stats['today_detected']}")
    print(f"Replies Published:       {stats['replies_posted']}")
    print(f"Drafts Awaiting Review:  {stats['needs_review']}")
    print(f"Drafts Ready:            {stats['pending_drafts']}")
    print(f"Latest Post ID:          {last_id or 'None'}")
    print(f"AUTO_POST_ENABLED:       {config.auto_post_enabled}")
    print(f"EMERGENCY_STOP:          {config.emergency_stop}")
    print("\nDISCOM Breakdown:")
    for discom, count in stats["discom_breakdown"].items():
        print(f"  {discom:12}: {count}")
    print("=" * 60)
    return 0


def cmd_test_routing(args: argparse.Namespace) -> int:
    """Interactively or programmatically test routing and classification on custom text."""
    config = load_config(config_path=args.config, env_path=args.env)
    classifier = GrievanceClassifier()
    router = DiscomRouter(config)

    text = args.text
    if not text:
        text = input("Enter sample complaint text: ").strip()

    print("\nAnalyzing text:\n" + f"'{text}'\n")

    c_res = classifier.classify(text)
    r_res = router.route(text)

    print("--- Classification Result ---")
    print(f"Is Complaint:   {c_res.is_complaint}")
    print(f"Picked Status:  {c_res.picked_status}")
    print(f"Complaint Type: {c_res.complaint_type or 'None'}")
    print(f"Language:       {c_res.language}")
    print(f"Shift:          {c_res.shift}")
    print(f"Confidence:     {c_res.confidence * 100:.1f}%")
    print(f"Reason:         {c_res.reason}")

    print("\n--- Routing Result ---")
    print(f"DISCOM:         {r_res.discom or 'Unresolved'}")
    print(f"Zone:           {r_res.zone or 'Unresolved'}")
    print(f"District:       {r_res.district or 'Unresolved'}")
    print(f"DISCOM Handle:  {r_res.discom_handle or 'None'}")
    print(f"Confidence:     {r_res.confidence}")
    print(f"Needs Review:   {r_res.needs_review}")
    print(f"Reasoning:      {r_res.reasoning}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="UPPCL X Complaint Monitoring & Google Sheets Management System")
    parser.add_argument("--config", help="Path to config.yaml", default=None)
    parser.add_argument("--env", help="Path to .env file", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sync
    p_sync = subparsers.add_parser("sync", help="Run complaint collection and sync cycle")
    p_sync.add_argument("--dry-run", action="store_true", help="Force dry-run mode (no Google Sheets writes, no X replies)")
    p_sync.add_argument("--daemon", action="store_true", help="Run continuously in background polling loop")
    p_sync.add_argument("--reset-watermark", action="store_true", help="Clear watermark before running to reprocess posts")
    p_sync.set_defaults(func=cmd_sync)

    # Status
    p_status = subparsers.add_parser("status", help="Show system status and database metrics")
    p_status.set_defaults(func=cmd_status)

    # Test Routing
    p_route = subparsers.add_parser("test-routing", help="Test classification and routing on a complaint snippet")
    p_route.add_argument("--text", help="Text to test", default=None)
    p_route.set_defaults(func=cmd_test_routing)

    args = parser.parse_args()
    setup_logging(args.verbose)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
