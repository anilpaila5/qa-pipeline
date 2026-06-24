"""
AI-powered test case generator.
Uses the Anthropic Claude API to generate structured test cases from
a Jira story's summary, description, and acceptance criteria.

Output is a list of dicts ready for csv_writer or the BrowserStack API:
  [
    {
      "name": "TC-001 — Verify default profile is selected",
      "description": "...",
      "preconditions": "...",
      "steps": "Step 1 | Step 2 | Step 3",
      "expected_result": "...",
      "priority": "High",
      "status": "Draft"
    },
    ...
  ]

Usage:
    gen = TestCaseGenerator(api_key="sk-ant-...")
    cases = gen.generate(story, folder_description="Login tests")
    for tc in cases:
        print(tc["name"])
"""

import json
import re
from typing import Any

import anthropic

GENERATION_PROMPT = """You are a senior QA engineer. Given the Jira story below, generate a
comprehensive set of test cases covering:
  - Positive / happy-path scenarios
  - Negative / error scenarios  
  - Boundary and edge cases
  - Permission and access-control scenarios (if applicable)
  - UI/UX validation (field labels, placeholders, error messages)

Jira Story
----------
Key: {key}
Summary: {summary}
Priority: {priority}

Description:
{description}

Acceptance Criteria:
{acceptance_criteria}

Output Format
-------------
Return ONLY a valid JSON array. No markdown fences, no explanations.
Each element must have exactly these keys:
  "name"            - Short title starting with the story key, e.g. "{key}_001 — Verify..."
  "description"     - One sentence describing what is being verified
  "preconditions"   - Setup needed before the test starts
  "steps"           - Steps as a pipe-delimited string: "Step 1 | Step 2 | Step 3"
  "expected_result" - What the system should do when steps succeed
  "priority"        - One of: Low, Medium, High, Critical
  "status"          - Always "Draft"

Generate between 10 and 30 test cases. Focus on quality and coverage,
not quantity. Do not generate duplicate scenarios.
"""


class TestCaseGenerator:
    """
    Calls the Anthropic Claude API to generate test cases from a Jira story.
    api_key is passed in at runtime — never stored on disk.
    """

    def __init__(self, api_key: str, model: str = "claude-opus-4-5") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(
        self, story: dict[str, Any], folder_description: str = ""
    ) -> list[dict[str, Any]]:
        """
        Generate test cases for the given Jira story dict
        (as returned by JiraClient.fetch_story).

        Returns a list of test case dicts.
        Raises ValueError if the AI response cannot be parsed as JSON.
        """
        prompt = GENERATION_PROMPT.format(
            key=story.get("key", "STORY"),
            summary=story.get("summary", ""),
            priority=story.get("priority", "Medium"),
            description=story.get("description", "(no description provided)"),
            acceptance_criteria=(
                story.get("acceptance_criteria", "")
                or "(no acceptance criteria found — use description)"
            ),
        )

        print(
            f"  🤖  Calling Claude ({self._model}) for {story.get('key', 'story')} …",
            flush=True,
        )

        message = self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        return self._parse_response(raw, story.get("key", "STORY"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str, issue_key: str) -> list[dict[str, Any]]:
        """
        Parse the AI response as a JSON array of test case dicts.
        Strips accidental markdown code fences if present.
        """
        # Strip ```json ... ``` fences if Claude wraps the output
        cleaned = re.sub(r"^```[a-z]*\s*", "", raw, flags=re.MULTILINE)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()

        try:
            cases = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Claude returned invalid JSON for {issue_key}: {exc}\n"
                f"Raw response (first 500 chars): {raw[:500]}"
            ) from exc

        if not isinstance(cases, list):
            raise ValueError(
                f"Expected a JSON array from Claude, got {type(cases).__name__}."
            )

        # Normalise each case — fill in missing keys with safe defaults.
        normalised = []
        for i, tc in enumerate(cases, start=1):
            if not isinstance(tc, dict) or not tc.get("name"):
                continue
            normalised.append(
                {
                    "name": tc.get("name", f"{issue_key}_{i:03d}"),
                    "description": tc.get("description", ""),
                    "preconditions": tc.get("preconditions", ""),
                    "steps": tc.get("steps", ""),
                    "expected_result": tc.get("expected_result", ""),
                    "priority": tc.get("priority", "Medium"),
                    "status": tc.get("status", "Draft"),
                }
            )

        return normalised

    def write_csv(
        self, test_cases: list[dict[str, Any]], output_path: str
    ) -> None:
        """
        Write generated test cases to a CSV file for human review
        before bulk-creating in BrowserStack.
        """
        import csv

        fieldnames = [
            "name",
            "description",
            "preconditions",
            "steps",
            "expected_result",
            "priority",
            "status",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(test_cases)

        print(f"  📝  {len(test_cases)} test cases written to: {output_path}")
        print(f"      Review and edit the CSV before publishing to BrowserStack.")
