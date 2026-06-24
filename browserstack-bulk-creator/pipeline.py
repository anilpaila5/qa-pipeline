#!/usr/bin/env python3
"""
End-to-End QA Pipeline
======================
Full workflow: Jira Story → AI Generation → CSV Review → BrowserStack Publish → Traceability

Usage:
  # Full pipeline (fetch + generate + publish)
  python pipeline.py --jira-issue QA-1831 --folder-id 49769713 --project-id 12345

  # Step 1 only: fetch + generate → write CSV for review, don't publish yet
  python pipeline.py --jira-issue QA-1831 --folder-id 49769713 --project-id 12345 --generate-only

  # Step 2 only: publish an already-reviewed CSV to BrowserStack
  python pipeline.py --csv input/QA-1831_cases.csv --folder-id 49769713 --project-id 12345 --publish-only

  # Show traceability report
  python pipeline.py --traceability-report

  # Export traceability to CSV
  python pipeline.py --traceability-report --report-csv traceability_export.csv

Run with --help for full options.
"""

import argparse
import getpass
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from ai_generator import TestCaseGenerator
from api_client import BrowserStackAPIError, BrowserStackClient
from checkpoint import Checkpoint
from config import DEFAULT_CONCURRENCY, FOLDER_MAPPINGS
from csv_reader import read_csv
from jira_fetcher import JiraClient, JiraFetchError
from notify import Notifier
from reporter import Reporter
from traceability import TraceabilityMap

DEFAULT_STATE_FILE = "state.json"
DEFAULT_TRACE_FILE = "traceability.json"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline: Jira → AI → BrowserStack → Traceability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python pipeline.py --jira-issue QA-1831 --folder-id 49769713 --project-id 12345

  # Generate only — write CSV for human review
  python pipeline.py --jira-issue QA-1831 --folder-id 49769713 --project-id 12345 --generate-only

  # Publish already-reviewed CSV
  python pipeline.py --csv input/QA-1831_cases.csv --folder-id 49769713 --project-id 12345 --publish-only

  # Show traceability coverage report
  python pipeline.py --traceability-report

  # With notifications
  python pipeline.py --jira-issue QA-1831 --folder-id 49769713 --project-id 12345 \\
      --webhook https://hooks.slack.com/... --webhook-type slack

  # Windows toast notification
  python pipeline.py --jira-issue QA-1831 --folder-id 49769713 --project-id 12345 --toast
        """,
    )

    # Jira source
    jira_grp = parser.add_argument_group("Jira")
    jira_grp.add_argument("--jira-issue", metavar="KEY",
                          help="Jira issue key, e.g. QA-1831")
    jira_grp.add_argument("--jira-url", metavar="URL",
                          help="Jira base URL, e.g. https://your-org.atlassian.net")
    jira_grp.add_argument("--jira-email", metavar="EMAIL",
                          help="Jira account email (Cloud). Omit to be prompted.")
    jira_grp.add_argument("--jira-pat", metavar="TOKEN",
                          help="Jira PAT for Server/DC auth. Omit to use email+token.")

    # AI generation
    ai_grp = parser.add_argument_group("AI Generation")
    ai_grp.add_argument("--model", default="claude-opus-4-5",
                        help="Anthropic model (default: claude-opus-4-5)")
    ai_grp.add_argument("--generate-only", action="store_true",
                        help="Generate CSV and stop — do not publish to BrowserStack.")
    ai_grp.add_argument("--output-csv", metavar="PATH",
                        help="Where to write the generated CSV (default: input/<KEY>_cases.csv).")

    # BrowserStack
    bs_grp = parser.add_argument_group("BrowserStack")
    bs_grp.add_argument("--project-id", type=int, metavar="ID",
                        help="BrowserStack project ID.")
    bs_grp.add_argument("--folder-id", type=int, metavar="ID",
                        help="BrowserStack folder ID to publish test cases into.")
    bs_grp.add_argument("--bs-username", metavar="USER",
                        help="BrowserStack username. Omit to be prompted.")

    # Publish-only (skip Jira + AI, use an existing CSV)
    pub_grp = parser.add_argument_group("Publish-only mode")
    pub_grp.add_argument("--publish-only", action="store_true",
                         help="Skip Jira fetch and AI generation; publish --csv directly.")
    pub_grp.add_argument("--csv", metavar="PATH",
                         help="CSV file to publish (required with --publish-only).")

    # Concurrency & state
    run_grp = parser.add_argument_group("Runtime")
    run_grp.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                         metavar="N",
                         help=f"Parallel workers for BrowserStack API (default: {DEFAULT_CONCURRENCY}).")
    run_grp.add_argument("--resume", action="store_true",
                         help="Skip test cases already created (reads state.json).")
    run_grp.add_argument("--dry-run", action="store_true",
                         help="Show what would happen; make no API calls.")
    run_grp.add_argument("--state-file", default=DEFAULT_STATE_FILE, metavar="PATH")
    run_grp.add_argument("--trace-file", default=DEFAULT_TRACE_FILE, metavar="PATH")

    # Notifications
    notif_grp = parser.add_argument_group("Notifications")
    notif_grp.add_argument("--webhook", metavar="URL",
                           help="Webhook URL for Slack/Teams notification on completion.")
    notif_grp.add_argument("--webhook-type", default="slack",
                           choices=["slack", "teams", "generic"],
                           help="Webhook format (default: slack).")
    notif_grp.add_argument("--toast", action="store_true",
                           help="Send a Windows desktop toast on completion.")

    # Reporting
    rep_grp = parser.add_argument_group("Reporting")
    rep_grp.add_argument("--traceability-report", action="store_true",
                         help="Print the traceability + coverage report and exit.")
    rep_grp.add_argument("--report-csv", metavar="PATH",
                         help="Export traceability map to a CSV file.")

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Credential collection helpers
# ---------------------------------------------------------------------------

def collect_jira_credentials(args: argparse.Namespace) -> JiraClient:
    """Prompt for Jira credentials and return a connected JiraClient."""
    jira_url = (args.jira_url or "").strip()
    if not jira_url:
        jira_url = input("  Jira base URL   : ").strip()

    if args.jira_pat:
        pat = args.jira_pat.strip()
        return JiraClient(base_url=jira_url, pat=pat)

    email = (args.jira_email or "").strip()
    if not email:
        email = input("  Jira email      : ").strip()
    api_token = getpass.getpass("  Jira API token  : ").strip()

    return JiraClient(base_url=jira_url, email=email, api_token=api_token)


def collect_anthropic_key() -> str:
    """Prompt for Anthropic API key (silent input)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        print("  Anthropic key   : (from ANTHROPIC_API_KEY env var)")
        return key
    return getpass.getpass("  Anthropic key   : ").strip()


def collect_bs_credentials(args: argparse.Namespace) -> tuple[str, str]:
    username = (args.bs_username or "").strip() or input("  BS username     : ").strip()
    access_key = getpass.getpass("  BS access key   : ").strip()
    return username, access_key


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_fetch_jira(args: argparse.Namespace) -> dict[str, Any]:
    """Step 1: Fetch Jira story."""
    print(f"\n── Step 1: Fetch Jira Story ({args.jira_issue}) ─────────────────")
    jira = collect_jira_credentials(args)

    print("  Validating Jira connection … ", end="", flush=True)
    if not jira.validate_connection():
        print("FAILED")
        print("  ✗ Cannot connect to Jira. Check URL and credentials.")
        sys.exit(1)
    print("OK")

    try:
        story = jira.fetch_story(args.jira_issue)
    except JiraFetchError as exc:
        print(f"  ✗ {exc}")
        sys.exit(1)

    print(f"  ✓  {story['key']}: {story['summary']}")
    print(f"     Priority  : {story['priority']}")
    print(f"     Status    : {story['status']}")
    if story["acceptance_criteria"]:
        ac_preview = story["acceptance_criteria"][:120].replace("\n", " ")
        print(f"     AC        : {ac_preview}…")
    return story


def step_generate(
    args: argparse.Namespace, story: dict[str, Any]
) -> tuple[list[dict[str, Any]], str]:
    """Step 2: Generate test cases via Claude and write CSV for review."""
    print("\n── Step 2: AI Test Case Generation ──────────────────────────────")

    anthropic_key = collect_anthropic_key()
    gen = TestCaseGenerator(api_key=anthropic_key, model=args.model)

    try:
        test_cases = gen.generate(story)
    except (ValueError, Exception) as exc:
        print(f"  ✗ Generation failed: {exc}")
        sys.exit(1)

    print(f"  ✓  Generated {len(test_cases)} test cases.")

    csv_path = args.output_csv or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "input",
        f"{story['key']}_cases.csv",
    )
    gen.write_csv(test_cases, csv_path)
    return test_cases, csv_path


def step_review_prompt(csv_path: str, dry_run: bool) -> bool:
    """
    Pause and ask the QA engineer to review the generated CSV.
    Returns True if they approve publishing, False to stop here.
    Skipped in dry-run mode (always returns False to prevent API calls).
    """
    if dry_run:
        print("\n  DRY-RUN: skipping review prompt — no publish will happen.")
        return False

    print(f"\n── Step 3: Human Review ─────────────────────────────────────────")
    print(f"  Generated CSV is at: {csv_path}")
    print()
    print("  Open the file, review and edit the test cases, then come back here.")
    print("  You can:")
    print("    • Edit test case names, steps, and expected results")
    print("    • Delete rows that are duplicates or out of scope")
    print("    • Add rows for scenarios the AI missed")
    print()
    answer = input("  Publish to BrowserStack now? [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def step_publish(
    args: argparse.Namespace,
    csv_path: str,
    jira_key: str,
    trace_map: TraceabilityMap,
    base_dir: str,
) -> Reporter:
    """Step 4: Publish approved test cases to BrowserStack."""
    print("\n── Step 4: BrowserStack Publish ────────────────────────────────")

    if not args.project_id or not args.folder_id:
        print("  ✗ --project-id and --folder-id are required for publishing.")
        sys.exit(1)

    print("\n  BrowserStack credentials:")
    username, access_key = collect_bs_credentials(args)

    client = BrowserStackClient(username, access_key, args.project_id)
    print("  Validating BrowserStack credentials … ", end="", flush=True)
    if not client.validate_credentials():
        print("FAILED")
        sys.exit(1)
    print("OK")

    state_path = os.path.join(base_dir, args.state_file)
    checkpoint = Checkpoint(state_path)
    reporter = Reporter()

    try:
        test_cases = read_csv(csv_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"  ✗ Cannot read CSV: {exc}")
        sys.exit(1)

    total = len(test_cases)
    reporter.start_file(os.path.basename(csv_path), args.folder_id)

    import threading
    _print_lock = threading.Lock()

    def tprint(*a: Any, **kw: Any) -> None:
        with _print_lock:
            print(*a, **kw)

    def worker(idx: int, tc: dict[str, Any]) -> None:
        name = tc["name"]
        label = f"[{idx}/{total}]"

        if args.resume and checkpoint.already_done(
            os.path.basename(csv_path), args.folder_id, name
        ):
            tc_id = checkpoint.get_tc_id(
                os.path.basename(csv_path), args.folder_id, name
            )
            tprint(f"  {label} ↷ Skipped: {tc_id or name}")
            reporter.record_success(name, {"id": tc_id, "_resumed": True})
            return

        try:
            response = client.create_test_case(args.folder_id, tc)
            tc_id = _extract_id(response)
            tprint(f"  {label} Created: {tc_id or 'OK'}  ←  {name}")
            checkpoint.mark_created(
                os.path.basename(csv_path), args.folder_id, name, tc_id
            )
            reporter.record_success(name, response)

            # Record in traceability map
            if jira_key and tc_id:
                trace_map.record(
                    jira_key=jira_key,
                    tc_name=name,
                    bs_tc_id=tc_id,
                    folder_id=args.folder_id,
                )
                trace_map.save()

        except BrowserStackAPIError as exc:
            tprint(f"  {label} ✗ API error for '{name}': {exc}")
            checkpoint.mark_failed(
                os.path.basename(csv_path), args.folder_id, name, str(exc)
            )
            reporter.record_failure(name, str(exc))

        except requests.RequestException as exc:
            msg = f"Network error: {exc}"
            tprint(f"  {label} ✗ {msg}")
            checkpoint.mark_failed(
                os.path.basename(csv_path), args.folder_id, name, msg
            )
            reporter.record_failure(name, msg)

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(worker, idx, tc): tc["name"]
            for idx, tc in enumerate(test_cases, start=1)
        }
        for future in as_completed(futures):
            exc = future.exception()
            if exc:
                tprint(f"  ✗ Unexpected error: {exc}")

    return reporter


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _extract_id(response: dict) -> str:
    for key in ("id", "tc_id", "test_case_id", "identifier"):
        if key in response:
            return str(response[key])
    return ""


def _build_notify_body(reporter: Reporter | None, jira_key: str) -> str:
    if reporter is None:
        return f"Pipeline complete for {jira_key}."
    fr = reporter._file_reports[-1] if reporter._file_reports else None
    if fr:
        return (
            f"Jira: {jira_key} | "
            f"Created: {fr.created}/{fr.total} | "
            f"Failed: {fr.failed}"
        )
    return f"Pipeline complete for {jira_key}."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))

    notifier = Notifier(
        webhook_url=args.webhook or "",
        webhook_type=args.webhook_type,
        toast=args.toast,
    )
    trace_map = TraceabilityMap(
        os.path.join(base_dir, args.trace_file)
    )

    # ── Traceability report only ──────────────────────────────────────────────
    if args.traceability_report:
        trace_map.print_coverage_report()
        if args.report_csv:
            trace_map.write_csv_report(args.report_csv)
        return

    print("=" * 62)
    print("  QA Pipeline: Jira → AI → BrowserStack → Traceability")
    print("=" * 62)

    reporter: Reporter | None = None
    jira_key = args.jira_issue or ""
    csv_path = ""

    # ── Publish-only: skip Jira + AI steps ───────────────────────────────────
    if args.publish_only:
        if not args.csv:
            print("✗ --publish-only requires --csv <path>.")
            sys.exit(1)
        csv_path = args.csv
        jira_key = os.path.splitext(os.path.basename(csv_path))[0].replace("_cases", "")
        print(f"  Mode        : Publish-only (skipping Jira + AI)")
        print(f"  CSV         : {csv_path}")

    else:
        # Full pipeline or generate-only
        if not args.jira_issue:
            print("✗ --jira-issue is required (or use --publish-only --csv).")
            sys.exit(1)

        # Step 1: Jira
        print("\n  Jira credentials:")
        story = step_fetch_jira(args)
        jira_key = story["key"]

        # Step 2: AI generate
        print("\n  Anthropic API key:")
        test_cases, csv_path = step_generate(args, story)

        if args.generate_only or args.dry_run:
            print(f"\n  ✓ CSV ready for review: {csv_path}")
            print(f"  Next step: run with --publish-only --csv {csv_path}"
                  " --folder-id ... --project-id ...")
            notifier.send(
                title=f"Test cases generated for {jira_key}",
                body=f"{len(test_cases)} draft cases written to {csv_path}",
                success=True,
            )
            return

        # Step 3: Human review
        approved = step_review_prompt(csv_path, args.dry_run)
        if not approved:
            print(f"\n  Stopping before publish. Review {csv_path} and re-run with:")
            print(f"  python pipeline.py --publish-only --csv {csv_path}"
                  f" --folder-id {args.folder_id} --project-id {args.project_id}")
            return

    # Step 4: Publish
    print("\n  BrowserStack credentials:")
    reporter = step_publish(args, csv_path, jira_key, trace_map, base_dir)
    reporter.print_summary()

    # Step 5: Traceability report
    trace_map.print_coverage_report()

    # Notify
    fr = reporter._file_reports[-1] if reporter._file_reports else None
    success = fr.failed == 0 if fr else False
    notifier.send(
        title=f"{'✅' if success else '❌'} BrowserStack publish complete — {jira_key}",
        body=_build_notify_body(reporter, jira_key),
        success=success,
    )


if __name__ == "__main__":
    main()
