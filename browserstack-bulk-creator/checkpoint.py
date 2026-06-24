"""
Checkpoint manager.
Persists per-case creation results to a JSON state file so interrupted
runs can be resumed without re-creating already-created test cases.

Thread-safe: all public methods acquire a reentrant lock before
mutating or reading shared state, so concurrent workers can call
mark_created / mark_failed simultaneously without data corruption.

State file format:
{
  "CreateObjectModalTestCases.csv": {
    "49769713": {
      "C_RENT23561_001 - Open Create Object Modal": {
        "status": "created",
        "tc_id": "TC-123456",
        "ts": "2026-06-24T10:15:00"
      }
    }
  }
}
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

_STATUS_CREATED = "created"
_STATUS_FAILED = "failed"


class Checkpoint:
    """
    Loads, queries, and updates a JSON checkpoint file.
    All public methods are thread-safe.
    """

    def __init__(self, state_path: str) -> None:
        self._path = state_path
        self._state: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load()

    # ------------------------------------------------------------------
    # Public API (all thread-safe)
    # ------------------------------------------------------------------

    def already_done(self, csv_file: str, folder_id: int, name: str) -> bool:
        """Return True if this test case was previously created successfully."""
        with self._lock:
            return (
                self._state.get(csv_file, {})
                .get(str(folder_id), {})
                .get(name, {})
                .get("status")
                == _STATUS_CREATED
            )

    def get_tc_id(self, csv_file: str, folder_id: int, name: str) -> str:
        """Return the stored TC ID for a previously created case (or empty string)."""
        with self._lock:
            return (
                self._state.get(csv_file, {})
                .get(str(folder_id), {})
                .get(name, {})
                .get("tc_id", "")
            )

    def mark_created(
        self, csv_file: str, folder_id: int, name: str, tc_id: str
    ) -> None:
        with self._lock:
            self._set(csv_file, folder_id, name, _STATUS_CREATED, tc_id=tc_id)
            self._save()

    def mark_failed(
        self, csv_file: str, folder_id: int, name: str, error: str
    ) -> None:
        with self._lock:
            self._set(csv_file, folder_id, name, _STATUS_FAILED, error=error)
            self._save()

    def count_done(self, csv_file: str, folder_id: int) -> int:
        with self._lock:
            return sum(
                1
                for v in self._state.get(csv_file, {}).get(str(folder_id), {}).values()
                if v.get("status") == _STATUS_CREATED
            )

    def clear_file(self, csv_file: str, folder_id: int) -> None:
        """Remove checkpoint entries for one CSV+folder pair (fresh re-run)."""
        with self._lock:
            self._state.setdefault(csv_file, {}).pop(str(folder_id), None)
            self._save()

    def exists(self) -> bool:
        return os.path.isfile(self._path)

    @property
    def path(self) -> str:
        return self._path

    # ------------------------------------------------------------------
    # Internal helpers (caller must hold self._lock)
    # ------------------------------------------------------------------

    def _set(
        self,
        csv_file: str,
        folder_id: int,
        name: str,
        status: str,
        tc_id: str = "",
        error: str = "",
    ) -> None:
        entry: dict[str, Any] = {
            "status": status,
            "tc_id": tc_id,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if error:
            entry["error"] = error
        (
            self._state
            .setdefault(csv_file, {})
            .setdefault(str(folder_id), {})[name]
        ) = entry

    def _load(self) -> None:
        if os.path.isfile(self._path):
            try:
                with open(self._path, encoding="utf-8") as fh:
                    self._state = json.load(fh)
            except (json.JSONDecodeError, OSError):
                print(
                    f"  ⚠ Warning: checkpoint file '{self._path}' could not be read "
                    f"— starting fresh."
                )
                self._state = {}

    def _save(self) -> None:
        """Atomic write: write to .tmp then rename so a crash never corrupts state."""
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh, indent=2)
        os.replace(tmp, self._path)
