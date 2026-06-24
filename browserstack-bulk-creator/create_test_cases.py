#!/usr/bin/env python3
"""
BrowserStack Test Management — Bulk Test Case Creator
======================================================
Reads CSV files from the input/ directory and creates test cases via the
BrowserStack REST API.

Usage:
  python create_test_cases.py --project-id <id>
  python create_test_cases.py --project-id <id> --dry-run
  python create_test_cases.py --project-id <id> --resume
  python create_test_cases.py --project-id <id> --concurrency 5
  python create_test_cases.py --project-id <id> --report results.csv
  python create_test_cases.py --project-id <id> --reset

Run with --help for full options.
"""

import argparse
import getpass
import json
import os
import sys
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

import requests

from api_client import BrowserStackAPIError, BrowserStackClient
from checkpoint import Checkpoint
from config import DEFAULT_CONCURRENCY, FOLDER_MAPPINGS, INPUT_DIR
from csv_reader import read_csv
from notify import Notifier
from reporter import Reporter

DEFAULT_STATE_FILE = "state.json"

# Global print lock — ensures each status line is written atomically even
# when multiple worker threads complete simultaneously.
_print_lock = threading.Lock()


def tprint(*args: Any, **kwargs: Any) -> None:
    """Thread-safe print."""
    with _print_lock:
        print(*args, **kwargs)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk-create BrowserStack Test Management test cases from CSV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_test_cases.py --project-id 12345
  python create_test_cases.py --project-id 12345 --dry-run
  python create_test_cases.py --project-id 12345 --resume
  python create_test_cases.py --project-id 12345 --concurrency 5
  python create_test_cases.py --project-id 12345 --file CreateGroupTestCases.csv
  python create_test_cases.py --project-id 12345 --report results.csv
  python create_test_cases.py --project-id 12345 --reset
        """,
    )
    parser.add_argument(
        "--project-id",
        required=True,
        type=int,
        help="BrowserStack project ID (integer).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print API payloads to stdout without making any API calls.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip test cases already marked as 'created' in state.json.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete state.json and start completely fresh. "
             "WARNING: previously created cases will be re-created.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        metavar="N",
        help=f"Number of parallel worker threads (default: {DEFAULT_CONCURRENCY}). "
             "Recommended: 3–5. Values above 10 may trigger BrowserStack rate limits.",
    )
    parser.add_argument(
        "--state-file",
        default=DEFAULT_STATE_FILE,
        metavar="PATH",
        help=f"Path to the checkpoint state file (default: {DEFAULT_STATE_FILE}).",
    )
    parser.add_argument(
        "--file",
        metavar="FILENAME",
        help="Process only this CSV file (must be listed in config.py).",
    )
    parser.add_argument(
        "--report",
        metavar="OUTPUT_CSV",
        help="Write a machine-readable CSV report to this path.",
    )
    parser.add_argument(
        "--username",
        help="BrowserStack username (omit to be prompted securely).",
    )

    notif_grp = parser.add_argument_group("Notifications")
    notif_grp.add_argument(
        "--webhook",
        metavar="URL",
        help="Webhook URL to notify on completion (Slack, Teams, or generic).",
    )
    notif_grp.add_argument(
        "--webhook-type",
        default="slack",
        choices=["slack", "teams", "generic"],
        help="Webhook payload format (default: slack).",
    )
    notif_grp.add_argument(
        "--toast",
        action="store_true",
        help="Send a Windows desktop toast notification on completion.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Credential collection
# ---------------------------------------------------------------------------

def collect_credentials(args: argparse.Namespace) -> tuple[str, str]:
    print("\n─── BrowserStack Credentials ───────────────────────────")
    if args.username:
        username = args.username.strip()
        print(f"  Username : {username}  (from --username flag)")
    else:
        username = input("  Username  : ").strip()

    access_key = getpass.getpass("  Access key: ").strip()

    if not username or not access_key:
        print("\n✗ Username and access key are both required.")
        sys.exit(1)

    print("────────────────────────────────────────────────────────\n")
    return username, access_key


# ---------------------------------------------------------------------------
# File selection
# ---------------------------------------------------------------------------

def resolve_files(requested_file: str | None) -> dict[str, dict]:
    if requested_file:
        if requested_file not in FOLDER_MAPPINGS:
            print(f"✗ '{requested_file}' is not listed in config.py FOLDER_MAPPINGS.")
            print(f"  Known files: {list(FOLDER_MAPPINGS.keys())}")
            sys.exit(1)
        return {requested_file: FOLDER_MAPPINGS[requested_file]}
    return FOLDER_MAPPINGS


# ---------------------------------------------------------------------------
# Per-case worker (runs inside ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _worker(
    *,
    idx: int,
    total: int,
    tc: dict[str, Any],
    folder_id: int,
    csv_name: str,
    client: BrowserStackClient,
    reporter: Reporter,
    checkpoint: Checkpoint,
    resume: bool,
) -> None:
    """
    Create one test case. Called concurrently by the thread pool.
    Uses tprint() for atomic console output.
    Checkpoint and Reporter are thread-safe.
    """
    name = tc["name"]
    label = f"[{idx}/{total}]"

    # ── Resume: skip already-created cases ──────────────────────────────
    if resume and checkpoint.already_done(csv_name, folder_id, name):
        tc_id = checkpoint.get_tc_id(csv_name, folder_id, name)
        tprint(f"  {label} ↷ Skipped (already created): {tc_id or name}")
        reporter.record_success(name, {"id": tc_id, "_resumed": True})
        return

    # ── Live API call ────────────────────────────────────────────────────
    try:
        response = client.create_test_case(folder_id, tc)
        tc_id = _extract_id(response)
        tprint(f"  {label} Created: {tc_id or 'OK'}  ←  {name}")
        checkpoint.mark_created(csv_name, folder_id, name, tc_id)
        reporter.record_success(name, response)

    except BrowserStackAPIError as exc:
        tprint(f"  {label} ✗ API error for '{name}': {exc}")
        checkpoint.mark_failed(csv_name, folder_id, name, str(exc))
        reporter.record_failure(name, str(exc))

    except requests.RequestException as exc:
        msg = f"Network error: {exc}"
        tprint(f"  {label} ✗ {msg} for '{name}'")
        checkpoint.mark_failed(csv_name, folder_id, name, msg)
        reporter.record_failure(name, msg)


# ---------------------------------------------------------------------------
# File processing (orchestrates workers)
# ---------------------------------------------------------------------------

def process_file(
    csv_name: str,
    mapping: dict,
    client: BrowserStackClient | None,
    reporter: Reporter,
    checkpoint: Checkpoint,
    dry_run: bool,
    resume: bool,
    concurrency: int,
    base_dir: str,
) -> None:
    folder_id: int = mapping["folder_id"]
    csv_path = os.path.join(base_dir, INPUT_DIR, csv_name)

    print(f"\n{'─'*60}")
    print(f"  File        : {csv_name}")
    print(f"  Folder      : {folder_id}  ({mapping['description']})")
    print(f"  Concurrency : {concurrency} worker(s)")
    print(f"{'─'*60}")

    try:
        test_cases = read_csv(csv_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"  ✗ Skipping — {exc}")
        return

    total = len(test_cases)
    if total == 0:
        print("  ⚠ No valid test cases found in file.")
        return

    already_done = checkpoint.count_done(csv_name, folder_id) if resume else 0
    if resume and already_done > 0:
        remaining = total - already_done
        print(f"  ↻ Resume mode: {already_done}/{total} already created, "
              f"{remaining} remaining.")

    reporter.start_file(csv_name, folder_id)

    # ── Dry-run: sequential, no threads needed ───────────────────────────
    if dry_run:
        for idx, tc in enumerate(test_cases, start=1):
            payload = {"folder_id": folder_id, "test_case": tc}
            print(f"  [{idx}/{total}] DRY-RUN payload for '{tc['name']}':")
            print(json.dumps(payload, indent=4))
            reporter.record_success(tc["name"], {"id": "DRY-RUN"})
        return

    # ── Live: submit all cases to the thread pool ─────────────────────────
    assert client is not None
    futures: dict[Future, str] = {}

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for idx, tc in enumerate(test_cases, start=1):
            future = executor.submit(
                _worker,
                idx=idx,
                total=total,
                tc=tc,
                folder_id=folder_id,
                csv_name=csv_name,
                client=client,
                reporter=reporter,
                checkpoint=checkpoint,
                resume=resume,
            )
            futures[future] = tc["name"]

        # Drain futures so any unhandled exceptions bubble up visibly.
        for future in as_completed(futures):
            exc = future.exception()
            if exc:
                name = futures[future]
                tprint(f"  ✗ Unexpected error for '{name}': {exc}")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _extract_id(response: dict) -> str:
    for key in ("id", "tc_id", "test_case_id", "identifier"):
        if key in response:
            return str(response[key])
    return ""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.concurrency < 1:
        print("✗ --concurrency must be at least 1.")
        sys.exit(1)

    files_to_process = resolve_files(args.file)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    state_path = os.path.join(base_dir, args.state_file)

    # ── Handle --reset ───────────────────────────────────────────────────────
    if args.reset:
        if os.path.isfile(state_path):
            os.remove(state_path)
            print(f"  ✓ Checkpoint file '{args.state_file}' deleted. Starting fresh.")
        else:
            print(f"  ⚠ No checkpoint file at '{args.state_file}' — nothing to reset.")

    # ── Header ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("  BrowserStack Bulk Test Case Creator")
    if args.dry_run:
        mode = "DRY-RUN — no API calls will be made"
    elif args.resume:
        mode = "RESUME — skipping already-created cases"
    else:
        mode = "LIVE"
    print(f"  Mode        : {mode}")
    print(f"  Project ID  : {args.project_id}")
    print(f"  Files       : {len(files_to_process)}")
    print(f"  Concurrency : {args.concurrency} worker(s)")
    print(f"  Checkpoint  : {args.state_file}")
    print("=" * 60)

    username, access_key = collect_credentials(args)

    # ── Validate credentials ─────────────────────────────────────────────────
    client: BrowserStackClient | None = None
    if not args.dry_run:
        client = BrowserStackClient(username, access_key, args.project_id)
        print("  Validating credentials … ", end="", flush=True)
        if not client.validate_credentials():
            print("FAILED")
            print("\n✗ Credentials appear invalid or project ID is wrong.")
            print("  Tip: run probe_api.py first to confirm the correct format.")
            sys.exit(1)
        print("OK")

    # ── Checkpoint ───────────────────────────────────────────────────────────
    checkpoint = Checkpoint(state_path)
    if args.resume and not checkpoint.exists():
        print(f"\n  ⚠ --resume specified but no checkpoint file found at "
              f"'{args.state_file}'. Running as a fresh batch.")

    reporter = Reporter()

    for csv_name, mapping in files_to_process.items():
        process_file(
            csv_name=csv_name,
            mapping=mapping,
            client=client,
            reporter=reporter,
            checkpoint=checkpoint,
            dry_run=args.dry_run,
            resume=args.resume,
            concurrency=args.concurrency,
            base_dir=base_dir,
        )

    reporter.print_summary()

    if args.report:
        reporter.write_csv_report(args.report)

    if not args.dry_run:
        print(f"  💾  Progress saved to: {args.state_file}")
        print(f"      Re-run with --resume to skip already-created cases.")

    # ── Notifications ─────────────────────────────────────────────────────────
    total_all = sum(fr.total for fr in reporter._file_reports)
    failed_all = sum(fr.failed for fr in reporter._file_reports)
    created_all = total_all - failed_all
    success = failed_all == 0

    Notifier(
        webhook_url=getattr(args, "webhook", "") or "",
        webhook_type=getattr(args, "webhook_type", "slack"),
        toast=getattr(args, "toast", False),
    ).send(
        title=f"{'✅' if success else '❌'} BrowserStack bulk creation complete",
        body=f"Processed: {total_all} | Created: {created_all} | Failed: {failed_all}",
        success=success,
    )


if __name__ == "__main__":
    main()
