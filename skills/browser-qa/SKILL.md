---
name: browser-qa
description: Drive a real browser through a UI flow with Playwright — navigate, click, fill, screenshot every step, and check network and console. Use when the user names a flow to run against a URL, or after a UI change lands and needs verifying in the browser.
---

## Input

- **Natural language flow**: "Create a recipe with 3 ingredients, verify nutrition calculates"
- **URL + instructions**: `http://localhost:3000/orders` + "Click New Order, fill supplier, submit"

If no URL provided, default to `http://localhost:3000`.

If a UI change just landed and no flow was named, ask: "What flow should I QA? (e.g., 'test the order creation at localhost:3000/orders')"

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

Parse the user's flow into numbered steps. Launch a **single subagent**.

Playwright MCP is the only driver. If Playwright MCP is unavailable, fall back to the `agent-browser` CLI.

### Subagent Prompt Template

> Execute the following QA test flow at {URL} using Playwright MCP tools. The browser session is already open at {URL} from the auth check.
>
> **Test steps:**
> {numbered steps from user's flow description}
>
> For EACH step:
> - `browser_snapshot` first — refs go stale the instant the page changes, so re-snapshot before EVERY interaction
> - Execute the interaction via Playwright MCP
> - Capture evidence: screenshot to `.qa/<NN>-<step-name>.png`, `browser_network_requests` after any API-triggering action, `browser_console_messages` for new errors. A step with no evidence is a FAIL.
>
> Report each step in the Step 4 format below. Every numbered step must appear with PASS or FAIL — a step you could not execute is FAIL, never omitted.
>
> **Teardown:** `browser_close`.

## Step 4: Report

```
QA: <flow description>

Step 1: <description>
  PASS — <observation>

Step 2: <description>
  PASS — <observation>
  API: POST /api/endpoint -> 201

Step 3: <description>
  FAIL — Expected X, got Y
  Screenshot: .qa/03-step-name.png

Console errors: <list or "none">
Screenshots: .qa/ (<N> files)

VERDICT: <ALL PASS | PARTIAL | FAIL> (N/M steps)
```

On failure: include exact expected vs actual and reference the screenshot.
