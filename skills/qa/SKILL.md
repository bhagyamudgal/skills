---
name: qa
description: Use when user says "qa", "test the flow", "QA this", "verify the UI", "test this page", "check if it works", "end-to-end check", or after completing code changes that affect UI and need manual verification replaced by automation.
---

# QA — Smart Browser Testing

Automates what a developer does manually: navigate, interact, trigger API calls, verify results. Uses Playwright MCP for interactions and agent-browser for video recording and visual diffs.

## Input

Accept either:
- **Natural language flow**: "Create a recipe with 3 ingredients, verify nutrition calculates"
- **URL + instructions**: `http://localhost:3000/orders` + "Click New Order, fill supplier, submit"

If no URL provided, default to `http://localhost:3000`.

## Step 1: Prepare

```bash
mkdir -p .qa
grep -qxF '.qa/' .gitignore 2>/dev/null || echo '.qa/' >> .gitignore
```

Check if dev server is running: `curl -s -o /dev/null -w "%{http_code}" <url>`. If not reachable, ask user to start it.

## Step 2: Auth Check

1. Navigate to URL via Playwright MCP `browser_navigate`
2. `browser_snapshot` the page
3. Look for login form indicators (input[type=password], /login in URL, auth-related text)
4. **If not logged in**: Tell user to log in manually in their browser, then say "done". Re-check after.
5. **If logged in**: Proceed to test execution.

## Step 3: Execute Test Flow

Parse the user's flow into numbered steps. Launch a **single subagent** that uses smart tool selection:

### Tool Selection Rules

| Task | Tool | Command |
|------|------|---------|
| Start video | agent-browser | `agent-browser open <url>` then `agent-browser record start .qa/recording.webm` |
| Navigate | Playwright MCP | `browser_navigate` |
| Get element refs | Playwright MCP | `browser_snapshot` (re-snapshot before EVERY interaction) |
| Click / Fill / Select | Playwright MCP | `browser_click`, `browser_fill_form`, `browser_select_option` |
| Wait for response | Playwright MCP | `browser_wait_for` |
| Check API calls | Playwright MCP | `browser_network_requests` |
| Check console errors | Playwright MCP | `browser_console_messages` with level "error" |
| Take screenshot | Playwright MCP | `browser_take_screenshot` with filename `.qa/<NN>-<step>.png` |
| Visual before/after diff | agent-browser | `agent-browser diff screenshot --baseline .qa/<before>.png` |
| Stop video | agent-browser | `agent-browser record stop` |

### Subagent Prompt Template

> Execute the following QA test flow at {URL}. Use Playwright MCP tools for all interactions and agent-browser for video recording.
>
> **Setup:**
> 1. `agent-browser open {URL}` — connect to the page
> 2. `agent-browser record start .qa/recording.webm` — start video
>
> **Test steps:**
> {numbered steps from user's flow description}
>
> For EACH step:
> - `browser_snapshot` first to get fresh element refs
> - Execute the interaction via Playwright MCP
> - `browser_take_screenshot` with filename `.qa/<NN>-<step-name>.png`
> - `browser_network_requests` after any action that triggers an API call
> - `browser_console_messages` to check for new errors
> - Report: PASS or FAIL with what was observed
>
> **Teardown:**
> 1. `agent-browser record stop` — save video
> 2. `browser_close` — close Playwright browser
> 3. `agent-browser close` — close agent-browser
>
> **Report format per step:**
> Step N: <description>
>   Result: PASS/FAIL
>   Observed: <what happened>
>   API: <method endpoint -> status> (if applicable)
>   Screenshot: .qa/<NN>-<step>.png
>   Errors: <console errors or "none">

## Step 4: Report

After the subagent completes, output the combined report:

```
======================================
QA: <flow description>
======================================

Step 1: <description>
  PASS — <observation>

Step 2: <description>
  PASS — <observation>
  API: POST /api/endpoint -> 201

Step 3: <description>
  FAIL — Expected X, got Y
  Screenshot: .qa/03-step-name.png

Console errors: <list or "none">
Video: .qa/recording.webm
Screenshots: .qa/ (<N> files)

======================================
VERDICT: <ALL PASS | PARTIAL | FAIL> (N/M steps)
======================================
```

On failure: include exact expected vs actual, reference the screenshot, and note the video has the full recording for debugging.

## Auto-trigger Usage

After completing code changes that affect UI, ask the user:

> "What flow should I QA? (e.g., 'test the order creation at localhost:3000/orders')"

Then run the full QA flow above.
