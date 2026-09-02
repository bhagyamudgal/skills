# Critic pass, verify steps

### 1. Dedupe

Merge findings describing the same issue across reviewers AND within a reviewer's output.

**Dedupe key**: `(file_path, post_image_line, normalized_symbol_name)`, NOT `Category`. For findings without a valid diff line, use `"file-level:<category>"` in place of `post_image_line` (e.g., `(config.ts, file-level:Architecture, missingvalidation)`). Two findings on the same `(file, line, symbol)` are duplicates regardless of category: merge, keep higher severity, concatenate reasoning.

Lowercase symbol names and strip CamelCase boundaries. `renderUserCard` becomes `renderusercard`.

Dedupe priority when merging:
1. Severity wins: `Critical > Serious > Moderate > Minor`.
2. Category precedence for ties: `Security > Reusability > Silent-failure > Breaking-change > Performance > DRY > Unnecessary > Intent > Architecture`.
3. Keep the highest confidence.
4. **Site list always survives.** When a cross-file finding (Subagent 3) merges with a
   single-file one, keep the UNION of their sites in `Class-sites`. Collapsing a
   "3 of 4 hooks handled" finding down to the one hook a chunk reviewer happened to cite
   re-creates the exact blind spot Subagent 3 exists to close.

### 1.5. Cheap line-count sanity

For each finding with a `File: <path:line>` reference, before expensive Step 2 verification:

1. Compute `max_valid_line(path)` from `gh pr view --json files`:
   - NEW file: `max_valid_line = file.additions`
   - MODIFIED file: `max_valid_line ≈ file.additions + file.deletions_original_side + ~200 buffer`. When suspicious, fetch HEAD file length via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>`.
   - Cheap heuristic: if `line > (file.additions + 500)` for a NEW file, almost certainly hallucinated.

2. If `cited_line > max_valid_line`: drop and log `hallucinated reference (line <N> exceeds <M> available)`. Drop it as cited. A line that doesn't exist is not rescued by shifting it to one that does.

### 2. Verify `file:line`

The full diff sits in main context, stashed in Phase 1. Main verifies references against it, independently of the subagent now-discarded context.

- For PRs under `< 500` lines, verify all findings.
- PRs `>= 500` lines: verify all Critical + Serious; for Moderate/Minor on files not fully stashed, fetch per-file patch:
  ```bash
  gh api repos/<owner>/<repo>/pulls/<num>/files --jq '.[] | select(.filename=="<path>") | .patch'
  ```
- **Routing.** Line-numbered findings go to line verification. Findings without a line number go to file-level verification. The two never mix.
- **Line verification.** `<path:line>` must point to a line on the **post-image / new side** of the hunk. Old-side-only references, deleted lines, or lines outside any hunk drop as `hallucinated reference`.
- **File-level verification.** Verify `path` appears in the PR changed files. A path outside the changed files drops as `hallucinated file reference`.

### 3. Drop already-known

If a finding matches "Prior findings" from Phase 1 AND is NOT marked `Prior-finding-correction`: DROP, log `already reported in prior review`.

### 4. Challenge with the 3-prong test

For each remaining finding, drop **only if all three** hold:
- (a) symptom is purely cosmetic or a nit
- (b) no user-visible behavior changes if ignored
- (c) no downstream refactor cost

Keep if **any one** fails. Log drops as `noise / 3-prong test`.

### 4.5. Reusability audit verification

For each reviewer Q6 No issues response, verify the audit. It catches a missing audit field, an insufficient search count, and uncounted class-method definitions.

#### 4.5a: Count new definitions in the diff

Match added lines (starting with `+`) against:

```
+\s*(export\s+(default\s+)?)?(async\s+)?(function|class|interface|type)\s+\w+
+\s*(export\s+)?const\s+\w+\s*(:\s*[^=]+)?=\s*(async\s+)?(\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>
+\s*(export\s+default\s+function|export\s+default\s+class|export\s+default\s+async\s+function)\s+\w+
+\s+(?:(?:private|protected|public|async|static)\s+)*\w+\s*\(
```

Patterns cover standard function/class/interface/type, arrow-function consts, default exports, and class methods inside class bodies for NestJS-style services, modifiers or not. Track `{`/`}` nesting from the nearest `class X {` to count only methods inside class blocks, and exclude control-flow keywords (`if`, `for`, `while`, `switch`, `catch`, `return`) and bare calls, which match the same shape without defining anything.

Combine into `new_definitions_count`.

#### 4.5b: Count and parse the audit

Match `(?:reusability|reuse)_searches?:` (canonical: `reusability_searches:`).

Three outcomes:

1. **Field entirely missing**: PROMPT NON-COMPLIANCE. Drop ALL Q6 "No issues" claims AND add a Serious finding "Reviewer did not include `reusability_searches:` audit, so Q6 was not performed."

2. **Field present with sentinel `N/A (no new definitions in diff)`**: verify `new_definitions_count == 0`. If holds, audit is valid. If not, treat as shallow per outcome 3.

3. **Field present with entries**: count entries. If `searches_count < new_definitions_count`, drop "Q6 No issues" claims AND add a Moderate finding "Reusability check was shallow (<S> searches for <N> new definitions). Manual scan recommended before merging."

   Additionally: for each entry where `N > 0` but `verified:` is missing or says `no`, mark the corresponding Q6a claim (if any) as low-confidence and log `search returned hits but reviewer did not verify semantic match`.

#### 4.5c: Log all drops to Filtered Out for auditability.

### 4.55. Class-completeness verification

For each surviving finding that proposes a code change, check its `class_completeness:` audit.
`Class-sites: <A>/<N>` counts the audit's `affected` sites over the total entries in its
`sites:` list. See "`class_completeness:` audit" in `references/finding-output-format.md`
for the vocabulary. `handled` is the state file's separate question and never appears here.

Steps 4.55 and 4.56 both run over the findings the step 6 gap check adds later, not only
over the ones the reviewers raised. See the routing note there. Every finding that
proposes a code change passes through this step; every finding carrying a `Suggested fix:`
passes through 4.56.

Batch every finding needing verification into **V1: Class-sweep verifier** and dispatch it
alongside V2/V3, within the 4-subagent cap and V1 batching in `<SKILL_DIR>/references/verification-subagents.md`. Main applies the rules below to what V1 returns.

1. **Field missing entirely**: the sweep was not run. Keep the finding and let V1 run the
   sweep. Derive the signature from `Rule-class`, and append V1's result to the finding. Log
   `class sweep run by verifier because the reviewer omitted the audit`.

2. **`verdict: INCOMPLETE`**: the reviewer found sites it did not report. Fold every
   unreported site into the finding's `Class-sites` count and list them in the finding
   body. A finding covering 1 of 4 sites, reported as if it covered the defect, is a
   cascade in waiting.

3. **`verdict: COMPLETE` with `search:` naming zero tool calls**: treat as missing (case 1).

4. **Shared-symbol escalation**: if the finding's file sits in a shared package (use the
   Phase 1 repo map) OR `Enclosing-symbol` is exported, its blast radius includes every
   caller. Where the sweep stopped at the defining file, run the caller search yourself
   and note the behavioral delta at each call site. Enumerate them before the fix ships,
   not after.

Every finding that enters this step leaves it, widened. Log every widening.

Done when every finding proposing a code change exits this step with a non-empty
`Class-sites`.

### 4.56. Inverse-risk verification

For each surviving finding with a `Suggested fix:`:

1. **`Inverse risk:` missing**: derive it yourself before printing. Ask what breaks if
   the suggestion is implemented literally and nothing else changes.

2. **Inverse risk is worse than the finding**: the suggestion is not a fix. Either
   rewrite it into one that doesn't trade the defect for a bigger one, or keep the
   finding and replace the suggestion with `no safe one-line fix, needs design`.

3. **Record it.** The `inverse_risk` string is persisted to `.claude/review-state/<pr>.yml`
   on the finding. Round N+1 checks it FIRST, before hunting anything new. See step 4.9.

`/fix-pr-review` implements these suggestions verbatim. An unvetted one-sentence
remedy becomes production code.

Done when every surviving finding carrying a `Suggested fix:` exits this step with a
non-empty `Inverse risk:`.
