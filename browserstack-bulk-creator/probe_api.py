#!/usr/bin/env python3
"""
BrowserStack Test Management — API Format Probe
================================================
Tries every plausible endpoint + payload combination and prints the full
HTTP response for each attempt.

GOAL: Find the one combination that returns HTTP 200 or 201 so the main
      script can use the confirmed-working format.

After you identify the winning variant, delete the "API_PROBE_DELETE_ME"
test case from the BrowserStack UI (one click).

Usage:
  python probe_api.py --project-id <id> --folder-id <id>

Example (using your real folder IDs):
  python probe_api.py --project-id 12345 --folder-id 49769713
"""

import argparse
import getpass
import json
import sys
import time

import requests
from requests.auth import HTTPBasicAuth

PROBE_NAME = "API_PROBE_DELETE_ME"

# ── Candidate base URLs ────────────────────────────────────────────────────────
BASE_URLS = [
    "https://test-management.browserstack.com/api/v1",
    "https://test-management.browserstack.com/api/v2",
]

# ── Candidate URL path patterns ─────────────────────────────────────────────────
# {base} + pattern.format(project_id=..., folder_id=...)
URL_PATTERNS = [
    "/projects/{project_id}/folders/{folder_id}/test-cases",
    "/projects/{project_id}/test-cases",
    "/projects/{project_id}/cases",
]

# ── Candidate payload shapes ────────────────────────────────────────────────────
PAYLOADS = [
    # Shape 1 — flat "name" key (most common REST convention)
    {
        "name": PROBE_NAME,
        "description": "Probe test — safe to delete",
    },
    # Shape 2 — nested under "test_case"
    {
        "test_case": {
            "name": PROBE_NAME,
            "description": "Probe test — safe to delete",
        }
    },
    # Shape 3 — "title" instead of "name"
    {
        "title": PROBE_NAME,
        "description": "Probe test — safe to delete",
    },
    # Shape 4 — flat with folder_id embedded
    {
        "name": PROBE_NAME,
        "description": "Probe test — safe to delete",
        "folder_id": None,  # filled in at runtime
    },
    # Shape 5 — BrowserStack TM legacy "data" wrapper
    {
        "data": {
            "name": PROBE_NAME,
            "description": "Probe test — safe to delete",
        }
    },
    # Shape 6 — with explicit "type" field (some TM APIs require it)
    {
        "name": PROBE_NAME,
        "description": "Probe test — safe to delete",
        "case_type": "other",
    },
]

PAYLOAD_LABELS = [
    'flat {"name": ...}',
    'nested {"test_case": {"name": ...}}',
    'flat {"title": ...}',
    'flat {"name": ..., "folder_id": ...}',
    'wrapped {"data": {"name": ...}}',
    'flat {"name": ..., "case_type": "other"}',
]


def collect_credentials(args: argparse.Namespace) -> tuple[str, str]:
    print("\n─── BrowserStack Credentials ───────────────────────────")
    username = args.username.strip() if args.username else input("  Username  : ").strip()
    access_key = getpass.getpass("  Access key: ").strip()
    if not username or not access_key:
        print("✗ Both username and access key are required.")
        sys.exit(1)
    print("────────────────────────────────────────────────────────\n")
    return username, access_key


def try_variant(
    session: requests.Session,
    auth: HTTPBasicAuth,
    url: str,
    payload: dict,
    label: str,
    variant_num: int,
    total: int,
) -> bool:
    """
    POST payload to url, print the full response, return True if successful.
    """
    print(f"\n{'─'*64}")
    print(f"  Variant {variant_num}/{total}")
    print(f"  URL    : {url}")
    print(f"  Shape  : {label}")
    print(f"  Payload: {json.dumps(payload, indent=4)}")
    print(f"{'─'*64}")

    try:
        resp = session.post(url, auth=auth, json=payload, timeout=15)
    except requests.RequestException as exc:
        print(f"  ✗ Network error: {exc}")
        return False

    print(f"  HTTP Status : {resp.status_code} {resp.reason}")
    print(f"  Response    : {resp.text[:800]}")

    if resp.status_code in (200, 201):
        print(f"\n  ✓ SUCCESS — This is the correct format!")
        return True

    time.sleep(0.5)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe BrowserStack TM API to find the correct endpoint + payload.",
    )
    parser.add_argument("--project-id", required=True, type=int)
    parser.add_argument("--folder-id", required=True, type=int)
    parser.add_argument(
        "--username",
        help="BrowserStack username (omit to be prompted).",
    )
    parser.add_argument(
        "--stop-on-success",
        action="store_true",
        default=True,
        help="Stop after the first successful variant (default: true).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Try ALL variants even after a success.",
    )
    args = parser.parse_args()

    username, access_key = collect_credentials(args)
    auth = HTTPBasicAuth(username, access_key)

    session = requests.Session()
    session.headers.update(
        {"Content-Type": "application/json", "Accept": "application/json"}
    )

    # Build the full list of (url, payload, label) combos
    combos: list[tuple[str, dict, str]] = []
    for base in BASE_URLS:
        for pattern in URL_PATTERNS:
            url = base + pattern.format(
                project_id=args.project_id, folder_id=args.folder_id
            )
            for payload_template, label in zip(PAYLOADS, PAYLOAD_LABELS):
                payload = dict(payload_template)  # shallow copy
                if "folder_id" in payload:
                    payload["folder_id"] = args.folder_id
                combos.append((url, payload, label))

    total = len(combos)
    print(f"Probing {total} combinations against project {args.project_id}, "
          f"folder {args.folder_id} …\n")
    print("A test case named 'API_PROBE_DELETE_ME' will be created on success.")
    print("Please delete it from the BrowserStack UI after the probe.\n")

    winners: list[tuple[str, str]] = []

    for i, (url, payload, label) in enumerate(combos, start=1):
        success = try_variant(session, auth, url, payload, label, i, total)
        if success:
            winners.append((url, label))
            if not args.all:
                break

    print("\n" + "=" * 64)
    if winners:
        print("  ✓  WINNING COMBINATION(S):")
        for url, label in winners:
            print(f"     URL   : {url}")
            print(f"     Shape : {label}")
        print()
        print("  NEXT STEP:")
        print("  1. Copy the winning URL and payload shape above.")
        print("  2. Run: python configure_format.py --url '<url>' --shape '<N>'")
        print("     (see instructions below) OR edit api_client.py directly.")
        print("  3. Delete 'API_PROBE_DELETE_ME' from the BrowserStack UI.")
        print("  4. Run the main script: python create_test_cases.py --project-id ...")
    else:
        print("  ✗  NO COMBINATION SUCCEEDED.")
        print()
        print("  Possible causes:")
        print("  1. Wrong project ID or folder ID.")
        print("  2. Wrong credentials (check username + access key in BrowserStack).")
        print("  3. Your account does not have Test Management enabled.")
        print("  4. BrowserStack changed their API — check:")
        print("     https://www.browserstack.com/docs/test-management/api")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
