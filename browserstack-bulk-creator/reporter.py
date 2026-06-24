"""
Summary reporter.
Collects per-file and per-case results, then prints a formatted report.

Thread-safe: record_success / record_failure acquire a lock so concurrent
workers can record results simultaneously without list corruption.
start_file() is always called from the main thread before workers start,
so it does not need locking.
"""

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    name: str
    success: bool
    tc_id: str = ""
    error: str = ""


@dataclass
class FileReport:
    csv_file: str
    folder_id: int
    results: list[CaseResult] = field(default_factory=list)

    @property
    def created(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def total(self) -> int:
        return len(self.results)


class Reporter:
    def __init__(self) -> None:
        self._file_reports: list[FileReport] = []
        self._current: FileReport | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording (thread-safe)
    # ------------------------------------------------------------------

    def start_file(self, csv_file: str, folder_id: int) -> None:
        """Call from the main thread before launching workers for a file."""
        self._current = FileReport(csv_file=csv_file, folder_id=folder_id)
        self._file_reports.append(self._current)

    def record_success(self, name: str, response: dict[str, Any]) -> None:
        tc_id = self._extract_id(response)
        with self._lock:
            assert self._current is not None
            self._current.results.append(
                CaseResult(name=name, success=True, tc_id=tc_id)
            )

    def record_failure(self, name: str, error: str) -> None:
        with self._lock:
            assert self._current is not None
            self._current.results.append(
                CaseResult(name=name, success=False, error=error)
            )

    # ------------------------------------------------------------------
    # Output (called from main thread only after all workers finish)
    # ------------------------------------------------------------------

    def print_summary(self) -> None:
        total_all = sum(r.total for r in self._file_reports)
        created_all = sum(r.created for r in self._file_reports)
        failed_all = sum(r.failed for r in self._file_reports)

        print("\n" + "=" * 60)
        print("  BULK CREATION SUMMARY")
        print("=" * 60)

        for fr in self._file_reports:
            status = "✓" if fr.failed == 0 else "✗"
            print(f"\n  {status}  {fr.csv_file}  (folder {fr.folder_id})")
            print(f"     Processed : {fr.total}")
            print(f"     Created   : {fr.created}")
            print(f"     Failed    : {fr.failed}")

            failures = [r for r in fr.results if not r.success]
            if failures:
                print("     Failures:")
                for f in failures:
                    print(f"       • {f.name} — {f.error}")

        print("\n" + "-" * 60)
        print(f"  TOTAL PROCESSED : {total_all}")
        print(f"  TOTAL CREATED   : {created_all}")
        print(f"  TOTAL FAILED    : {failed_all}")
        print("=" * 60 + "\n")

    def write_csv_report(self, output_path: str) -> None:
        """Write a machine-readable CSV report for CI/CD pipelines."""
        import csv

        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["csv_file", "folder_id", "name", "status", "tc_id", "error"]
            )
            for fr in self._file_reports:
                for r in fr.results:
                    writer.writerow(
                        [
                            fr.csv_file,
                            fr.folder_id,
                            r.name,
                            "created" if r.success else "failed",
                            r.tc_id,
                            r.error,
                        ]
                    )
        print(f"  📄  Report written to: {output_path}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_id(response: dict[str, Any]) -> str:
        for key in ("id", "tc_id", "test_case_id", "identifier"):
            if key in response:
                return str(response[key])
        return ""
