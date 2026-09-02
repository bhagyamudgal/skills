---
name: browser-qa
description: Drive a real browser through a UI flow with Playwright. Navigate, click, fill, screenshot every step, and check network and console. Use when the user names a flow to run against a URL, or after a UI change lands and needs verifying in the browser.
---

I drive a real browser through the flow and I do not call it done until I watched it work. Every step gets a screenshot, API-triggering actions get a network check, and I read the console for new errors.

## Input

- A natural language flow, for example "Create a recipe with 3 ingredients, verify nutrition calculates".
- A URL plus instructions, for example `http://localhost:3000/orders` plus "Click New Order, fill supplier, submit".

When no URL is provided, I default to `http://localhost:3000`.

When a UI change just landed and no flow was named, I ask what flow to QA, for example "test the order creation at localhost:3000/orders".

## Step 1: Prepare

```bash
mkdir -p .qa
[ -s .gitignore ] && [ -n "$(tail -c1 .gitignore)" ] && printf '\n' >> .gitignore
grep -qxF '.qa/' .gitignore 2>/dev/null || printf '.qa/\n' >> .gitignore
```

I check whether the dev server is running with `curl -s -o /dev/null -w "%{http_code}" <url>`. When it is not reachable, I ask the user to start it.

## Step 2: Auth Check

1. I navigate to the URL through Playwright MCP `browser_navigate`.
2. I take a `browser_snapshot` of the page.
3. I look for login form indicators, things like input[type=password], /login in the URL, or auth-related text.
4. When the session is not logged in, I tell the user to log in manually in their browser, then say "done". I re-check after.
5. When the session is logged in, I proceed to test execution.

## Step 3: Execute Test Flow

I parse the user flow into numbered steps and launch a single subagent.

Playwright MCP is the only driver. When Playwright MCP is unavailable, I fall back to the `agent-browser` CLI.

### Mutation preflight (main agent, before dispatch)

I settle this before the subagent exists. A dispatched subagent has no channel to the user, so a `confirmation-required` verdict raised inside it would strand the run with the browser open and nobody to answer it.

When the URL is production-like or any parsed step mutates shared data, I invoke `preflight-mutations` here. I pass the exact environment URL, authenticated account and workspace, action and record IDs, ownership, pre-test record snapshot, restoration or compensation steps, and user authorization. I apply its result contract in the main agent. On `confirmation-required` I present the card and get that decision from the user before dispatching. On `blocked` I report its **Next action** and dispatch nothing. Only a `ready` card is interpolated into the prompt below as `{ready card}`.

Local flows that touch only disposable data do not use this gate. I pass `not-applicable, local flow, disposable data only` as `{ready card}`.

### Subagent prompt template

> Execute the following QA test flow at {URL} using Playwright MCP tools. The browser session is already open at {URL} from the auth check.
>
> Test steps. {numbered steps from the user flow description}.
>
> Mutation authorization. {ready card}.
>
> That card is already authorized. Do not invoke `preflight-mutations` yourself, since you have no way to answer what it may ask. For every shared-state interaction, re-read and compare that target current guards immediately before the write. Continue under the card while they match. When a guard changed, stop the pending interaction and return the unexecuted remainder to the main agent for re-preflight instead of writing. After the write, run the card authoritative read-back, advance the guards from the observed state, and record the item as `landed`, `failed`, or `reconcile-required`. An ambiguous result is `reconcile-required`. Stop that item and report it for resolution from authoritative state. Never retry it yourself.
>
> For EACH step, take a `browser_snapshot` first. Refs go stale the instant the page changes, so re-snapshot before EVERY interaction. Execute the interaction through Playwright MCP. Capture evidence as a screenshot to `.qa/<NN>-<step-name>.png`, with `browser_network_requests` after any API-triggering action and `browser_console_messages` for new errors. A step with no evidence is a FAIL.
>
> Report each step in the Step 4 format below. Every numbered step must appear with PASS or FAIL. A step you could not execute is FAIL, never omitted.
>
> Teardown. `browser_close`.

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

On failure I include the exact expected versus actual and reference the screenshot.
