"""
CSV reader module.
Reads test case definitions from CSV files and returns structured data.

Expected CSV columns (case-insensitive):
  name          - Test case title (required)
  description   - Plain-text description
  preconditions - Setup steps before the test runs
  steps         - Test steps, pipe-delimited ( Step 1 | Step 2 | Step 3 )
  expected_result - What success looks like
  priority      - Low / Medium / High / Critical  (default: Medium)
  status        - Draft / Ready / Deprecated      (default: Draft)
"""

import csv
import os
from typing import Any

REQUIRED_COLUMNS = {"name"}
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_STATUSES = {"Draft", "Ready", "Deprecated"}


def _normalise_headers(raw_headers: list[str]) -> dict[str, str]:
    """Return a mapping of lowercased-stripped header → original header."""
    return {h.strip().lower(): h for h in raw_headers}


def _parse_steps(raw: str) -> list[dict[str, str]]:
    """
    Convert a pipe-delimited steps string into the BrowserStack step format.
    Each pipe-separated segment becomes one step.
    """
    if not raw or not raw.strip():
        return []
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    return [{"step": step, "expected_result": ""} for step in parts]


def _validate_priority(value: str, row_num: int) -> str:
    candidate = value.strip().title() if value else "Medium"
    if candidate not in VALID_PRIORITIES:
        print(f"  ⚠  Row {row_num}: unknown priority '{value}', defaulting to 'Medium'")
        return "Medium"
    return candidate


def _validate_status(value: str, row_num: int) -> str:
    candidate = value.strip().title() if value else "Draft"
    if candidate not in VALID_STATUSES:
        print(f"  ⚠  Row {row_num}: unknown status '{value}', defaulting to 'Draft'")
        return "Draft"
    return candidate


def read_csv(filepath: str) -> list[dict[str, Any]]:
    """
    Read a CSV file and return a list of test case dicts ready for the API.
    Raises FileNotFoundError if the file is missing.
    Raises ValueError if required columns are absent.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    test_cases: list[dict[str, Any]] = []

    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            raise ValueError(f"CSV file is empty or has no headers: {filepath}")

        norm = _normalise_headers(list(reader.fieldnames))

        missing = REQUIRED_COLUMNS - set(norm.keys())
        if missing:
            raise ValueError(
                f"CSV '{filepath}' is missing required columns: {missing}. "
                f"Found columns: {list(norm.keys())}"
            )

        for row_num, raw_row in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items()}

            name = row.get("name", "").strip()
            if not name:
                print(f"  ⚠  Row {row_num}: 'name' is empty, skipping.")
                continue

            steps_raw = row.get("steps", "")
            steps = _parse_steps(steps_raw)

            test_cases.append(
                {
                    "name": name,
                    "description": row.get("description", ""),
                    "preconditions": row.get("preconditions", ""),
                    "steps": steps,
                    "expected_result": row.get("expected_result", ""),
                    "priority": _validate_priority(row.get("priority", ""), row_num),
                    "status": _validate_status(row.get("status", ""), row_num),
                }
            )

    return test_cases
