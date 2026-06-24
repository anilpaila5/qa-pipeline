"""
Traceability mapper.
Records and queries the three-way mapping:

  Jira Story ↔ BrowserStack Test Case ID ↔ Automation Method

Stored in traceability.json (alongside state.json).

This answers the questions management will ask:
  - Which Jira stories have test cases in BrowserStack?
  - Which BrowserStack TCs are covered by automation?
  - Which stories have zero test coverage?

Usage:
    tm = TraceabilityMap("traceability.json")
    tm.record(
        jira_key="QA-1831",
        tc_name="QA-1831_001 — Verify default profile",
        bs_tc_id="TC-47647",
        folder_id=49769713,
        automation_method="",   # fill in later when automated
    )
    tm.save()

    for entry in tm.by_jira("QA-1831"):
        print(entry["bs_tc_id"], entry["automation_method"])

    tm.print_coverage_report()
"""

import csv
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

_DEFAULT_PATH = "traceability.json"


class TraceabilityMap:
    """
    Persistent, thread-safe mapping of Jira stories → BrowserStack TCs.
    Entries are appended; existing entries for the same bs_tc_id are updated.
    """

    def __init__(self, path: str = _DEFAULT_PATH) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        jira_key: str,
        tc_name: str,
        bs_tc_id: str,
        folder_id: int,
        automation_method: str = "",
        automation_file: str = "",
    ) -> None:
        """
        Add or update a traceability entry.
        If a record with the same (jira_key, bs_tc_id) exists it is updated;
        otherwise a new entry is appended.
        """
        with self._lock:
            for entry in self._entries:
                if entry["jira_key"] == jira_key and entry["bs_tc_id"] == bs_tc_id:
                    entry["tc_name"] = tc_name
                    entry["folder_id"] = folder_id
                    entry["automation_method"] = automation_method
                    entry["automation_file"] = automation_file
                    entry["updated_at"] = _now()
                    return

            self._entries.append(
                {
                    "jira_key": jira_key,
                    "tc_name": tc_name,
                    "bs_tc_id": bs_tc_id,
                    "folder_id": folder_id,
                    "automation_method": automation_method,
                    "automation_file": automation_file,
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            )

    def save(self) -> None:
        """Atomically write the current state to disk."""
        with self._lock:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._entries, fh, indent=2)
            os.replace(tmp, self._path)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def by_jira(self, jira_key: str) -> list[dict[str, Any]]:
        """Return all entries for a given Jira issue key."""
        with self._lock:
            return [e for e in self._entries if e["jira_key"] == jira_key]

    def by_bs_id(self, bs_tc_id: str) -> dict[str, Any] | None:
        """Return the entry for a given BrowserStack TC ID, or None."""
        with self._lock:
            for e in self._entries:
                if e["bs_tc_id"] == bs_tc_id:
                    return dict(e)
            return None

    def all_jira_keys(self) -> list[str]:
        """Return unique Jira keys that have at least one mapped TC."""
        with self._lock:
            return sorted({e["jira_key"] for e in self._entries})

    def coverage_stats(self) -> dict[str, Any]:
        """Return high-level coverage numbers."""
        with self._lock:
            total = len(self._entries)
            automated = sum(1 for e in self._entries if e.get("automation_method"))
            stories = len({e["jira_key"] for e in self._entries})
            return {
                "total_test_cases": total,
                "automated": automated,
                "not_automated": total - automated,
                "automation_coverage_pct": round(
                    (automated / total * 100) if total else 0, 1
                ),
                "jira_stories_covered": stories,
            }

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def print_coverage_report(self) -> None:
        stats = self.coverage_stats()
        print("\n" + "=" * 60)
        print("  TRACEABILITY & COVERAGE REPORT")
        print("=" * 60)
        print(f"  Jira stories with test cases  : {stats['jira_stories_covered']}")
        print(f"  Total BrowserStack test cases : {stats['total_test_cases']}")
        print(f"  Automated                     : {stats['automated']}")
        print(f"  Not yet automated             : {stats['not_automated']}")
        print(
            f"  Automation coverage           : {stats['automation_coverage_pct']}%"
        )
        print()

        for jira_key in self.all_jira_keys():
            entries = self.by_jira(jira_key)
            automated = sum(1 for e in entries if e.get("automation_method"))
            print(f"  {jira_key}  —  {len(entries)} TCs  "
                  f"({automated} automated, {len(entries) - automated} manual)")
            for e in entries:
                auto = e.get("automation_method") or "—"
                print(f"    • {e['bs_tc_id']}  {e['tc_name'][:55]}  [{auto}]")

        print("=" * 60 + "\n")

    def write_csv_report(self, output_path: str) -> None:
        """Write the full mapping to a CSV for sharing with management."""
        with self._lock:
            entries = list(self._entries)

        fieldnames = [
            "jira_key", "bs_tc_id", "tc_name", "folder_id",
            "automation_method", "automation_file", "created_at", "updated_at",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(entries)

        print(f"  📄  Traceability report written to: {output_path}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if os.path.isfile(self._path):
            try:
                with open(self._path, encoding="utf-8") as fh:
                    self._entries = json.load(fh)
            except (json.JSONDecodeError, OSError):
                print(
                    f"  ⚠ Warning: could not read '{self._path}' — starting fresh."
                )
                self._entries = []


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
