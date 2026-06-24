"""
BrowserStack Test Management API client.
Handles authentication, request execution, and error handling.

Retry strategy (tenacity):
  - Retries on transient HTTP errors (429, 5xx) and network failures.
  - Does NOT retry on permanent errors (400, 401, 403, 404) — those
    indicate a bug in the payload or credentials and won't fix themselves.
  - Uses exponential back-off: 1 s → 2 s → 4 s … up to RETRY_WAIT_MAX.
  - Respects the Retry-After header when the API returns 429.
  - Prints a clear message on every retry attempt so the user can see
    the script is not hung.

Credentials are injected at construction time and never written to disk.
"""

import threading
import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    BROWSERSTACK_API_BASE,
    RATE_LIMIT_DELAY,
    REQUEST_TIMEOUT,
    RETRYABLE_STATUS_CODES,
    RETRY_MAX_ATTEMPTS,
    RETRY_WAIT_INITIAL,
    RETRY_WAIT_MAX,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BrowserStackAPIError(Exception):
    """Raised when the API returns a non-2xx response that is NOT retryable."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class RetryableAPIError(Exception):
    """
    Raised for transient HTTP errors (429, 5xx).
    tenacity catches this class and schedules a retry.
    The Retry-After header value (seconds) is stored so the wait strategy
    can honour it.
    """

    def __init__(self, status_code: int, message: str, retry_after: float = 0) -> None:
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"HTTP {status_code} (transient): {message}")


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------

def _before_retry(retry_state: RetryCallState) -> None:
    """Called by tenacity before each retry — prints a visible warning."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    attempt = retry_state.attempt_number

    wait = getattr(retry_state, "next_action", None)
    wait_secs = round(wait.sleep if wait else 0, 1)

    if isinstance(exc, RetryableAPIError) and exc.retry_after > 0:
        wait_secs = exc.retry_after

    code = getattr(exc, "status_code", "network")
    print(
        f"      ⟳  Attempt {attempt} failed ({code}). "
        f"Retrying in {wait_secs} s …"
    )


def _retry_after_from_exc(exc: RetryableAPIError) -> float:
    """Return the Retry-After value from the exception (0 if not set)."""
    return exc.retry_after


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class BrowserStackClient:
    """
    Thin wrapper around the BrowserStack Test Management REST API.

    All calls use HTTPS Basic Auth (username + access_key).
    Transient errors are retried with exponential back-off via tenacity.
    Permanent errors (4xx except 429) surface immediately as
    BrowserStackAPIError.
    """

    def __init__(self, username: str, access_key: str, project_id: int) -> None:
        self._auth = HTTPBasicAuth(username, access_key)
        self._project_id = project_id
        # Thread-local storage: each worker thread gets its own Session so
        # concurrent requests never share connection state.
        self._local = threading.local()

    @property
    def _session(self) -> requests.Session:
        """Return (or lazily create) a per-thread requests.Session."""
        if not hasattr(self._local, "session"):
            s = requests.Session()
            s.headers.update(
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
            self._local.session = s
        return self._local.session

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def validate_credentials(self) -> bool:
        """
        Ping the projects endpoint to verify credentials before any writes.
        Returns True on 200/201, False on anything else (including network err).
        """
        url = f"{BROWSERSTACK_API_BASE}/projects/{self._project_id}"
        try:
            resp = self._session.get(url, auth=self._auth, timeout=REQUEST_TIMEOUT)
            return resp.status_code in (200, 201)
        except requests.RequestException:
            return False

    def create_test_case(
        self, folder_id: int, test_case: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Create a single test case inside the given folder.

        Automatically retries on transient errors (429, 5xx, network timeouts)
        up to RETRY_MAX_ATTEMPTS total attempts with exponential back-off.

        Args:
            folder_id:  BrowserStack folder ID.
            test_case:  Normalised test case dict from csv_reader.

        Returns:
            The API response body (dict).

        Raises:
            BrowserStackAPIError: permanent failure (400/401/403/404).
            RetryableAPIError: all retries exhausted for a transient failure.
            requests.RequestException: network-level error after all retries.
        """
        url = (
            f"{BROWSERSTACK_API_BASE}/projects/{self._project_id}"
            f"/folders/{folder_id}/test-cases"
        )
        payload = self._build_payload(test_case)
        return self._post_with_retry(url, payload)

    # ------------------------------------------------------------------
    # Retry-decorated inner method
    # ------------------------------------------------------------------

    @retry(
        reraise=True,
        retry=retry_if_exception_type((RetryableAPIError, requests.RequestException)),
        stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=RETRY_WAIT_INITIAL,
            min=RETRY_WAIT_INITIAL,
            max=RETRY_WAIT_MAX,
        ),
        before_sleep=_before_retry,
    )
    def _post_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Inner POST — decorated with tenacity retry logic.
        Separated from create_test_case() so tenacity only wraps the HTTP call,
        not the payload-building or rate-limit sleep.
        """
        resp = self._session.post(
            url, auth=self._auth, json=payload, timeout=REQUEST_TIMEOUT
        )

        if resp.status_code in (200, 201):
            time.sleep(RATE_LIMIT_DELAY)
            return self._safe_json(resp)

        body = self._safe_json(resp)
        message = body.get("message", resp.text[:300])

        if resp.status_code in RETRYABLE_STATUS_CODES:
            # Honour Retry-After header (BrowserStack sends it on 429).
            retry_after = self._parse_retry_after(resp)
            if retry_after > 0:
                print(f"      ⏳  Rate-limited. Server says wait {retry_after} s.")
                time.sleep(retry_after)
            raise RetryableAPIError(resp.status_code, message, retry_after)

        # Permanent error — don't retry.
        raise BrowserStackAPIError(resp.status_code, message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(tc: dict[str, Any]) -> dict[str, Any]:
        """Convert the normalised test-case dict to the API payload shape."""
        payload: dict[str, Any] = {
            "name": tc["name"],
            "description": tc.get("description", ""),
            "preconditions": tc.get("preconditions", ""),
            "priority": tc.get("priority", "Medium"),
            "status": tc.get("status", "Draft"),
        }

        steps = tc.get("steps", [])
        if steps:
            payload["test_case_steps"] = steps
        elif tc.get("expected_result"):
            payload["test_case_steps"] = [
                {"step": "See description", "expected_result": tc["expected_result"]}
            ]

        return payload

    @staticmethod
    def _parse_retry_after(resp: requests.Response) -> float:
        """
        Parse the Retry-After response header.
        Returns seconds to wait, or 0 if the header is absent or unparseable.
        BrowserStack may send it as an integer number of seconds.
        """
        raw = resp.headers.get("Retry-After", "")
        try:
            return max(0.0, float(raw))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _safe_json(resp: requests.Response) -> dict[str, Any]:
        try:
            return resp.json()
        except ValueError:
            return {}
