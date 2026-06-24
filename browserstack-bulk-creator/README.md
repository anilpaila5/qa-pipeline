# BrowserStack Bulk Test Case Creator — Full QA Pipeline

A Python utility that covers the complete path from requirements to managed test cases:

```
Jira Story → AI Generation → Human Review → BrowserStack Publish → Traceability Map
```

---

## One-time setup

```bat
:: Install Python 3.10+
winget install Python.Python.3.12

:: Install all dependencies
pip install -r requirements.txt
```

---

## Two ways to use this

### Option A — Full Pipeline (recommended)

Fetch a Jira story, generate test cases with Claude, review the CSV, then publish.

```bat
pipeline.bat QA-1831 <project_id> <folder_id>
```

You'll be prompted for:
- Jira URL, email, API token
- Anthropic API key (for Claude)
- BrowserStack username + access key

### Option B — Bulk CSV Creator (original utility)

Publish hand-authored CSV files directly to BrowserStack with no AI or Jira step.

```bat
run.bat <project_id>
```

---

## Pipeline — Step by Step

### Step 1 — Jira Integration

The pipeline fetches the story automatically — no copy-paste:
- Summary, description, acceptance criteria
- Priority, status, labels, components

### Step 2 — AI Test Case Generation

Claude generates structured test cases covering:
- Positive / happy-path scenarios
- Negative / error scenarios
- Boundary and edge cases
- Permission and access-control scenarios
- UI/UX field validation

The output is a **draft CSV** in `input/<issue_key>_cases.csv`.

### Step 3 — Human Review *(critical)*

You are prompted to open the CSV and review before anything is published:
- Edit test case names, steps, expected results
- Delete duplicates or out-of-scope cases
- Add scenarios the AI missed

This is the governance step. Managers trust the output because a human signed off.

### Step 4 — BrowserStack Publish

Approved cases are pushed to BrowserStack in parallel (configurable concurrency).
Each case is saved to `state.json` immediately — interruptions are safe.

### Step 5 — Traceability Map

Every Jira key ↔ BrowserStack TC ID mapping is stored in `traceability.json`.
Later, add the automation method name as cases get automated:

```
QA-1831  →  TC-47647  →  verifyDefaultSearchProfile()
QA-1831  →  TC-47648  →  verifyNoProfileIndicator()
```

---

## Pipeline Commands

```bat
:: Full pipeline (all 5 steps)
pipeline.bat QA-1831 12345 49769713

:: Generate only — write CSV for review, stop before BrowserStack
pipeline.bat QA-1831 12345 49769713 --generate-only

:: Publish a reviewed CSV (skip Jira + AI)
pipeline.bat --publish-only input\QA-1831_cases.csv 12345 49769713

:: Traceability + coverage report
pipeline.bat --report

:: Export traceability to CSV
python pipeline.py --traceability-report --report-csv traceability_export.csv

:: With Slack notification on completion
pipeline.bat QA-1831 12345 49769713 --webhook https://hooks.slack.com/...

:: With Teams notification
pipeline.bat QA-1831 12345 49769713 --webhook https://... --webhook-type teams

:: With Windows desktop toast
pipeline.bat QA-1831 12345 49769713 --toast

:: With 5 parallel workers
pipeline.bat QA-1831 12345 49769713 --concurrency 5
```

---

## Notifications

The script sends a completion notification automatically if a channel is configured.
No channel = terminal output only (always active).

| Channel | Flag | Example |
|---|---|---|
| Slack | `--webhook <url>` | `--webhook https://hooks.slack.com/...` |
| Teams | `--webhook <url> --webhook-type teams` | — |
| Custom JSON | `--webhook <url> --webhook-type generic` | — |
| Windows toast | `--toast` | No URL needed — uses PowerShell |

Works on both the pipeline (`pipeline.bat`) and the bulk CSV creator (`run.bat`).

---

## Bulk CSV Creator Commands

The original utility still works unchanged — no Jira or AI needed.

```bat
:: Live run — all configured CSV files
run.bat 12345

:: Dry-run — print payloads, make no API calls
run.bat 12345 --dry-run

:: 5 parallel workers
run.bat 12345 --concurrency 5

:: Resume after interruption
run.bat 12345 --resume

:: Start completely fresh (delete state.json)
run.bat 12345 --reset

:: With Slack notification
run.bat 12345 --webhook https://hooks.slack.com/... --webhook-type slack

:: With Windows toast
run.bat 12345 --toast
```

---

## Concurrency — Parallel Workers

```bat
:: Default: sequential (safe, no rate-limit risk)
run.bat 12345

:: 5 workers — ~5x faster
run.bat 12345 --concurrency 5
```

Recommended: **3–5**. The retry logic handles 429s automatically but fewer workers
means fewer rate-limit hits.

---

## Resume After Interruption

Progress is saved to `state.json` after every successful API call.

```bat
:: After a crash or Ctrl+C, just add --resume
run.bat 12345 --resume
pipeline.bat QA-1831 12345 49769713 --resume
```

---

## Retry Behaviour

| Error type | Action |
|---|---|
| 429 Rate Limited | Waits `Retry-After` seconds, then retries |
| 500 / 502 / 503 / 504 | Exponential back-off: 1 s → 2 s → 4 s |
| Network timeout | Same back-off |
| 400 / 401 / 403 / 404 | Fails immediately — retrying won't help |

Max 4 attempts per case. Failures are saved to `state.json` — `--resume` retries them.

---

## First time? Confirm the API format works

Previous API attempts failed due to unknown payload format. Run the probe first:

```bat
probe.bat <project_id> 49769713
```

---

## Traceability Report

```bat
pipeline.bat --report
```

Answers:
- Which Jira stories have test cases in BrowserStack?
- Which BrowserStack TCs are covered by automation?
- What is the automation coverage percentage?

To update automation coverage, edit `traceability.json` and fill in `automation_method`
and `automation_file` fields for each TC that has been automated.

---

## Adding New CSV Files (bulk mode)

1. Create a CSV in `input/` (copy an existing one as a template).
2. Add an entry to `FOLDER_MAPPINGS` in `config.py`.
3. Run `run.bat <project_id>`.

---

## CSV Format

| Column | Required | Default |
|---|---|---|
| `name` | ✓ | — |
| `description` | | `""` |
| `preconditions` | | `""` |
| `steps` | | `[]` — pipe-separated: `Step 1 \| Step 2` |
| `expected_result` | | `""` |
| `priority` | | `Medium` |
| `status` | | `Draft` |

---

## Project Files

| File | Purpose |
|---|---|
| **Pipeline** | |
| `pipeline.py` | End-to-end orchestrator (Jira→AI→BS→Traceability) |
| `pipeline.bat` | Windows launcher for the pipeline |
| `jira_fetcher.py` | Jira REST API client |
| `ai_generator.py` | Claude test case generator |
| `traceability.py` | Jira ↔ BrowserStack ↔ Automation mapping |
| `notify.py` | Slack / Teams / Windows toast notifications |
| **Bulk CSV Creator** | |
| `create_test_cases.py` | Entry point for CSV-only bulk creation |
| `run.bat` | Windows launcher for bulk CSV creation |
| `config.py` | Folder-ID mappings, API constants, retry/concurrency config |
| `csv_reader.py` | CSV parsing and validation |
| `api_client.py` | BrowserStack REST API wrapper (retry + thread-local sessions) |
| `checkpoint.py` | Resume-after-interruption state (thread-safe) |
| `reporter.py` | Progress display and summary reporting (thread-safe) |
| `probe_api.py` | API format discovery — run first if API calls fail |
| `probe.bat` | Windows launcher for the probe |
| `input/*.csv` | Test case definitions |
| **State files (generated)** | |
| `state.json` | Checkpoint state for `--resume` |
| `traceability.json` | Jira ↔ BrowserStack ↔ Automation mapping |
| `ARCHITECTURE.md` | Full architecture review and integration guide |
