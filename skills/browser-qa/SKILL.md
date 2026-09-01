---
name: browser-qa
description: Drive a real browser through a UI flow with Playwright. Navigate, click, fill, screenshot every step, and check network and console. Use when the user names a flow to run against a URL, or after a UI change lands and needs verifying in the browser.
---

## Input

- **Natural language flow**: "Create a recipe with 3 ingredients, verify nutrition calculates"
- **URL + instructions**: `http://localhost:3000/orders` + "Click New Order, fill supplier, submit"

If no URL provided, default to `http://localhost:3000`.

If a UI change just landed and no flow was named, ask: "What flow should I QA? (e.g., 'test the order creation at localhost:3000/orders')"

## Step 1: Prepare

```bash
mkdir -p .qa
[ -s .gitignore ] && [ -n "$(tail -c1 .gitignore)" ] && printf '\n' >> .gitignore
grep -qxF '.qa/' .gitignore 2>/dev/null || printf '.qa/\n' >> .gitignore
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

### Mutation preflight (main agent, before dispatch)

Settle this before the subagent exists. A dispatched subagent has no channel to the user, so a `confirmation-required` verdict raised inside it would strand the run with the browser open and nobody to answer it.

If {URL} is production-like or any parsed step mutates shared data, invoke `preflight-mutations` here. Pass the exact environment URL, authenticated account/workspace, action and record IDs, ownership, pre-test record snapshot, restoration/compensation steps, and user authorization. Apply its result contract in the main agent: on `confirmation-required`, present the card and get that decision from the user before dispatching; on `blocked`, report its **Next action** and dispatch nothing. Only a `ready` card is interpolated into the prompt below as `{ready card}`.

Local flows that touch only disposable data do not use this gate. Pass `not-applicable, local flow, disposable data only` as `{ready card}`.

### Subagent Prompt Template

> Execute the following QA test flow at {URL} using Playwright MCP tools. The browser session is already open at {URL} from the auth check.
>
> **Test steps:**
> {numbered steps from user's flow description}
>
> **Mutation authorization:** {ready card}
>
> That card is already authorized. Do not invoke `preflight-mutations` yourself; you have no way to answer what it may ask. For every shared-state interaction, re-read and compare that target's current guards immediately before the write. Continue under the card while they match. If a guard changed, stop the pending interaction and return the unexecuted remainder to the main agent for re-preflight instead of writing. After the write, run the card's authoritative read-back, advance the guards from the observed state, and record the item as `landed`, `failed`, or `reconcile-required`. An ambiguous result is `reconcile-required`: stop that item and report it for resolution from authoritative state; never retry it yourself.
>
> For EACH step:
> - `browser_snapshot` first. Refs go stale the instant the page changes, so re-snapshot before EVERY interaction
> - Execute the interaction via Playwright MCP
> - Capture evidence: screenshot to `.qa/<NN>-<step-name>.png`, `browser_network_requests` after any API-triggering action, `browser_console_messages` for new errors. A step with no evidence is a FAIL.
>
> Report each step in the Step 4 format below. Every numbered step must appear with PASS or FAIL. A step you could not execute is FAIL, never omitted.
>
> **Teardown:** `browser_close`.

## Step 4: Report

```
QA: <flow description>

Step 1: <description>
  PASS: <observation>

Step 2: <description>
  PASS: <observation>
  API: POST /api/endpoint -> 201

Step 3: <description>
  FAIL: Expected X, got Y
  Screenshot: .qa/03-step-name.png

Console errors: <list or "none">
Screenshots: .qa/ (<N> files)

VERDICT: <ALL PASS | PARTIAL | FAIL> (N/M steps)
```

On failure: include exact expected vs actual and reference the screenshot.
