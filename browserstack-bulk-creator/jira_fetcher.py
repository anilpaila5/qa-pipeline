"""
Jira REST API client.
Fetches story details (summary, description, acceptance criteria, priority,
labels, components) from a Jira Cloud or Server instance.

Authentication: API token (Jira Cloud) or PAT (Jira Server/DC).
Credentials are prompted at runtime and never stored.

Usage:
    client = JiraClient(base_url="https://your-org.atlassian.net",
                        email="you@company.com",
                        api_token="...")
    story = client.fetch_story("QA-1831")
    print(story["summary"])
    print(story["acceptance_criteria"])
"""

import re
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class JiraFetchError(Exception):
    """Raised when the Jira API returns an unexpected response."""


class JiraClient:
    """
    Minimal Jira REST v3 client for reading story data.
    Supports both Jira Cloud (email + API token) and Jira Server/DC
    (username + password or PAT via bearer token).
    """

    def __init__(
        self,
        base_url: str,
        email: str = "",
        api_token: str = "",
        pat: str = "",
    ) -> None:
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

        if pat:
            # Jira Server/DC Personal Access Token (bearer)
            self._session.headers["Authorization"] = f"Bearer {pat}"
        elif email and api_token:
            # Jira Cloud: email + API token via Basic Auth
            self._session.auth = HTTPBasicAuth(email, api_token)
        else:
            raise ValueError("Provide either (email + api_token) or pat.")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def fetch_story(self, issue_key: str) -> dict[str, Any]:
        """
        Return a structured dict for the given Jira issue.

        Keys:
          key, summary, description, acceptance_criteria,
          priority, status, labels, components, story_points,
          raw_fields (full API response fields dict)
        """
        url = f"{self._base}/rest/api/3/issue/{issue_key}"
        params = {
            "fields": (
                "summary,description,priority,status,labels,"
                "components,story_points,customfield_10016,"   # story points
                "customfield_10014,"                           # epic link
                "customfield_10034,"                           # acceptance criteria (common)
                "customfield_10300,"                           # AC (alt field)
            )
        }

        try:
            resp = self._session.get(url, params=params, timeout=20)
        except requests.RequestException as exc:
            raise JiraFetchError(f"Network error fetching {issue_key}: {exc}") from exc

        if resp.status_code == 404:
            raise JiraFetchError(
                f"Issue '{issue_key}' not found. "
                "Check the issue key and your Jira base URL."
            )
        if resp.status_code == 401:
            raise JiraFetchError(
                "Jira authentication failed. "
                "Check your email/API token or PAT."
            )
        if resp.status_code not in (200, 201):
            raise JiraFetchError(
                f"Jira API returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        fields = data.get("fields", {})

        return {
            "key": data.get("key", issue_key),
            "summary": fields.get("summary", ""),
            "description": self._extract_text(fields.get("description")),
            "acceptance_criteria": self._extract_ac(fields),
            "priority": (fields.get("priority") or {}).get("name", "Medium"),
            "status": (fields.get("status") or {}).get("name", ""),
            "labels": fields.get("labels", []),
            "components": [c["name"] for c in fields.get("components", [])],
            "story_points": (
                fields.get("story_points")
                or fields.get("customfield_10016")
                or fields.get("customfield_10014")
            ),
            "raw_fields": fields,
        }

    def validate_connection(self) -> bool:
        """Quick connectivity check — returns True if credentials work."""
        try:
            resp = self._session.get(
                f"{self._base}/rest/api/3/myself", timeout=10
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_ac(self, fields: dict[str, Any]) -> str:
        """
        Extract acceptance criteria from common custom field locations.
        Different Jira configurations use different custom field IDs.
        """
        for key in ("customfield_10034", "customfield_10300", "customfield_10301"):
            raw = fields.get(key)
            if raw:
                text = self._extract_text(raw)
                if text:
                    return text

        # Some teams embed AC in the description after a heading.
        description = self._extract_text(fields.get("description"))
        return self._extract_ac_from_text(description)

    @staticmethod
    def _extract_ac_from_text(text: str) -> str:
        """Look for 'Acceptance Criteria' section in plain text."""
        match = re.search(
            r"acceptance criteria[:\s]+(.*?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_text(node: Any) -> str:
        """
        Convert Atlassian Document Format (ADF) or plain string to text.
        ADF is the JSON format Jira Cloud uses for rich-text fields.
        """
        if node is None:
            return ""
        if isinstance(node, str):
            return node

        # ADF document node
        if isinstance(node, dict):
            content_type = node.get("type", "")
            if content_type == "text":
                return node.get("text", "")
            parts = []
            for child in node.get("content", []):
                parts.append(JiraClient._extract_text(child))
            separator = "\n" if content_type in ("paragraph", "bulletList") else " "
            return separator.join(p for p in parts if p).strip()

        return str(node)
