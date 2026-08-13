# Agent Session Recommendation Ledger

This is the authoritative source and recovery map for turning the 12 August 2026 Agent Session Retrospective into durable agent behavior. Resume by reading this file and executing `NEXT ACTION`; conversation memory and summaries are not run state.

## Run state

- **Objective:** Process every recommendation in source order. For each item, finish a `grill-me` design tree, obtain explicit confirmation of shared understanding, write the agreed artifact with `writing-for-agents`, verify it at its acceptance surface, and update this ledger before advancing.
- **Current item:** `R05 — Surface-aware done`
- **NEXT ACTION:** Complete the R05 overlap scan against `done` and acceptance-surface workflows, then grill the smallest unresolved design frontier.
- **Progress:** 4 of 18 recommendations complete; 1 researching; 13 pending.
- **Canonical artifact:** `docs/agent_session_recommendations.md`
- **Source artifact:** Agent Session Retrospective, local research artifact dated 12 August 2026, served at `http://127.0.0.1:4173/` when captured.
- **Last updated:** 13 August 2026

### Working contract

1. Preserve source evidence in this ledger; later summaries supplement it.
2. Process one recommendation at a time in the order below unless the user explicitly changes the order.
3. Research environmental facts before asking the user. Ask the complete current decision frontier through `grill-me`; dependent decisions wait for a later round.
4. Treat the retrospective's destination as a proposal. The grill may conclude that the right result is a new skill, an amendment, shared reference, global rule, project rule, decision record, consolidation, or decline.
5. Begin implementation only after the grill frontier is empty and the user confirms shared understanding.
6. Write agent-consumed artifacts with `writing-for-agents`; for skills, also apply its skill mechanics and validate the final invocation surface.
7. Change an item's status only when its exit criterion is met. Record decisions, artifact paths, and verification evidence in that item's detail section.
8. Update `NEXT ACTION`, counts, the status table, item detail, and change log together after every material transition.
9. Keep delivery proportional: use the repository's existing verifier and focused examples; add a bespoke evaluator only when a safety-critical behavior cannot be checked otherwise. Stop after one implementation review and one affected-area recheck unless new evidence changes the artifact.

### Status vocabulary

| Status | Entry condition | Exit criterion |
|---|---|---|
| `pending` | Source recommendation recorded; no active work | Item becomes the sole active item |
| `researching` | Environmental facts or overlap are being resolved | Facts needed by the grill are recorded |
| `grilling` | At least one design decision is open | Frontier is empty and user confirms shared understanding |
| `decided` | Design is confirmed | Implementation begins, or decision requires no implementation |
| `implementing` | Agreed artifact is being changed | Requested changes are present |
| `verifying` | Implementation is present | Acceptance-surface checks pass and evidence is recorded |
| `complete` | All item criteria are satisfied | Terminal |
| `blocked` | Progress requires unavailable authority or external state | Blocker is removed and prior active status resumes |
| `declined` | User explicitly decides not to implement | Terminal; rationale required |

## Status board

| ID | Priority | Source recommendation | Proposed destination | Status | Final artifact | Next gate |
|---|---|---|---|---|---|---|
| R01 | P0 | Evidence-backed claim gate | Skill | `complete` | `skills/verify-claims/` | Complete |
| R02 | P0 | External-state mutation preflight | Skill | `complete` | `skills/preflight-mutations/` | Complete |
| R03 | P0 | Calibrated project-board mutation | Skill | `complete` | `skills/calibrate-board-mutations/` | Complete |
| R04 | P0 | Review-ledger convergence | Skill | `complete` | `skills/converge-reviews/` | Complete |
| R05 | P0 | Surface-aware done | Skill | `researching` | TBD | Resolve overlap |
| R06 | P1 | Bounded unattended orchestrator | Skill | `pending` | TBD | Start after R05 closes |
| R07 | P1 | Claude ↔ Codex setup sync | Skill | `pending` | TBD | Start after R06 closes |
| R08 | P1 | Structured decision ledger | Skill | `pending` | TBD | Start after R07 closes |
| R09 | P1 | Ticket evidence preservation | Skill | `pending` | TBD | Start after R08 closes |
| R10 | P1 | Artifact lifecycle manager | Skill | `pending` | TBD | Start after R09 closes |
| R11 | P1 | Merge-readiness evidence card | Skill | `pending` | TBD | Start after R10 closes |
| R12 | P1 | Non-interactive tooling canary | Skill | `pending` | TBD | Start after R11 closes |
| R13 | P1 | Material-state progress updates | Global rules | `pending` | TBD | Start after R12 closes |
| R14 | P1 | Evidence reuse and ownership | Global rules | `pending` | TBD | Start after R13 closes |
| R15 | P0 | GSM3 operating facts | Project rules | `pending` | TBD | Start after R14 closes |
| R16 | P1 | Spanical landing conventions | Project rules | `pending` | TBD | Start after R15 closes |
| R17 | P1 | Fileseye skill-change canary | Project rules | `pending` | TBD | Start after R16 closes |
| R18 | P2 | Fact-bound personal drafting | Decision log | `pending` | TBD | Start after R17 closes |

## Source record

### Overview

**Headline:** Rigor is strong. Control systems around it are the bottleneck.

The agents routinely catch subtle defects, work test-first, and handle Git safely. The recurring cost comes from calibrating too late, losing scope across long orchestration chains, verifying an internal proxy instead of the user-facing outcome, and repeating review work without a shared ledger.

| Measure | Value | Detail |
|---|---:|---|
| Human-facing sessions | 112 | 102 manually filtered Claude sessions plus 10 historical Codex root sessions |
| Human turns | 1,061 | 1,003 Claude turns plus 58 genuine user messages in Codex roots |
| Clear rectification episodes | 23 | 16 manually confirmed Claude episodes and at least 7 Codex episodes |
| Long Claude sessions | 42 | Five or more human turns; 30 reached ten or more and 12 reached twenty or more |

Coverage was 6 April–12 August 2026. Raw files extended to 18 March, but earlier Claude records were plugin telemetry or generated noise. No human conversations were locally present in May or June. “All time” means all history then stored on the machine; deleted, remote-only, and unlogged sessions were unrecoverable.

### Correction patterns

#### Mutating before calibrating

- **Signal:** The costliest correction in the archive.
- **Evidence:** On 12 August, Codex wrote 108 GSM3 board estimates totaling 1,507.5 hours before agreeing on an agent-assisted estimation unit. User anchors forced a rewrite to 232 hours for 68 user-owned tickets. One intermediate summary also misstated 258.5 hours before self-correcting.
- **Implication:** High-volume external mutations need a representative preview, explicit unit, owner boundary, and ledger-derived totals before the first write.

#### Scope and intent drift

- **Signal:** 79 Claude turns across 33 Claude sessions restated scope.
- **Evidence:** Episodes included committing unrequested SQL docs, misunderstanding that an issue should be anonymized but still posted, ignoring a preferred grilling workflow, starting investigation-only tickets despite an end-to-end requirement, and dropping draft orders whose empty state was necessary for adding articles.
- **Implication:** Turn scope into an explicit working contract and check the diff or mutation against it.

#### Verification at the wrong boundary

- **Signal:** Internal checks passed while the user-facing outcome did not.
- **Evidence:** Migrated skills passed filesystem and discovery checks but were absent from the invocation surface the user expected. Other conclusions changed after reinspection of current code, real logs, local data, screenshots, or the browser.
- **Implication:** Verify at the acceptance boundary: browser for UI, live re-fetch for board writes, picker and manual invocation for skills, and real data for data claims.

#### Progress-state opacity

- **Signal:** At least 33 human-facing sessions needed progress reassurance.
- **Evidence:** The user repeatedly asked variants of “where are we?”, “what is left?”, “continue”, and “why are you waiting?”. Dense status narration did not provide a durable completed/active/blocked/next ledger.
- **Implication:** Replace narration with material state transitions and a compact ledger that survives compaction and agent turnover.

#### Over-orchestration and review churn

- **Signal:** 95 historical Codex subagent files across 10 roots.
- **Evidence:** The heaviest roots spawned 39, 25, and 12 descendants. Stable diffs sometimes received implementer reviews, root-level done reviews, and another convergence pass. Claude sessions warned against duplicate ownership and review rounds that generated further rounds.
- **Implication:** Add ownership, diff-hash invalidation, retry limits, and a shared findings ledger to parallel work.

#### Platform migration optimized abstractions before parity

- **Signal:** Two direct corrections in the first Codex root.
- **Evidence:** The Claude-to-Codex migration distilled and renamed workflows before inventorying custom, portable constructs. The user corrected the assumption that `/done` was Claude-native and asked to settle the global `AGENTS.md` first.
- **Implication:** Preserve familiar behavior first; simplify only with explicit agreement.

#### External-state preflight gaps

- **Signal:** Rare, high-impact corrections across Git and ticket workflows.
- **Evidence:** Claude deleted a stacked PR base branch and closed its dependent PR, amended published history where the user wanted a corrective commit, and inferred issue grouping before previewing it. Repairs came after shared state changed.
- **Implication:** Resolve exact target, dependencies, ownership, reversibility, and requested action before mutating GitHub, boards, or published history; preview ambiguous restructuring.

#### Source evidence gets summarized away

- **Signal:** 34 artifact turns across 11 Claude sessions.
- **Evidence:** Ticket extraction omitted teammates' text, comments, and screenshots; consolidation risked dropping findings; two competing artifacts remained after a claimed consolidation.
- **Implication:** Let summaries supplement source evidence. Preserve provenance, successor links, and one authoritative-artifact marker through every split or consolidation.

### Strengths to preserve

#### Independent review catches real defects

- **Signal:** Consequential findings in all three major Spanical code flows.
- **Evidence:** Reviews caught timezone/cache overreach, response-body timeout gaps, broad retry classification, retry-hook error leakage, exact cutoff leakage, missing-repository coverage, and ambiguous measured-zero semantics before merge.
- **Implication:** Keep independent review; improve convergence and evidence reuse.

#### Root-cause and test-first work is strong

- **Signal:** Consistent in standalone Codex bug roots.
- **Evidence:** Agents established failing tests, fixed behavior at public seams, and reran targeted and full checks. One regression test proved persisted cache state changed rather than checking output totals alone.
- **Implication:** Preserve this as the default for bug fixes.

#### Git safety is disciplined

- **Signal:** Repeated across publishing and merge roots.
- **Evidence:** Exact SHA guards, force-with-lease, dependency-order merges, merge-commit policy, clean-worktree checks, and backup-before-symlink behavior were applied consistently.
- **Implication:** Preserve these patterns in PR and stacked-PR skills.

#### Limitations are reported honestly

- **Signal:** Observed across at least five technical Codex roots.
- **Evidence:** Agents separated pre-existing failures from regressions and disclosed skipped checks, rate limits, unavailable tools, and known follow-ups.
- **Implication:** Extend verified-versus-assumed reporting to user-facing acceptance criteria.

### Project distribution

| Project | Human-facing sessions | Claude turns | Platform mix |
|---|---:|---:|---|
| gastro-smart/GSM3 | 58 | 706 | 54 Claude + 4 Codex |
| hexleap/znift | 17 | 114 | 16 Claude + 1 Codex |
| gloo/gloo-work-portal | 13 | 33 | Claude only |
| hexleap/spanical | 10 | 66 | 5 Claude + 5 Codex |
| hexleap/fileseye | 7 | 32 | Claude only |
| worktree-cli | 4 | 10 | Claude only |
| Personal, Myganger, drmmai | 3 | 42 | One Claude session each |

### Method and confidence

- **Corpus:** Inventoried 2,424 Claude JSONL files and 109 Codex files. The primary denominator used 102 retained Claude human sessions and 10 historical Codex roots.
- **Filtering:** Excluded Claude subagents, plugin logs, evals, temporary probes, agent worktrees, generated SDK runs, and noise. Excluded this audit from Codex, used ten user-facing roots as the denominator, and treated 95 child sessions only as operational evidence.
- **Discovery:** An automated fingerprint pass found 136 broader histories including replay variants. It guided manual discovery but did not define the conversation count.
- **Classification:** Manually inspected strict and broad matches for course correction, explicit fault, scope, verification, tooling, quality, and progress.
- **Caveats:** A terminal message is not proof of user acceptance. Tool errors are usually diagnostic telemetry. Long sessions have more exposure. Model comparisons were omitted because date, project, and task mix are confounded.
- **Privacy:** The report contains no credentials, raw client data, emails, or full sensitive prompts. Evidence is aggregated or paraphrased.

## Recommendation details and decisions

### R01 — Evidence-backed claim gate

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Claude's strongest recurring correction theme was an inference becoming a claim before code, data, browser, or log evidence agreed.
- **Source specification:**
  - Record claim and counter-hypothesis.
  - Require code-path plus empirical evidence.
  - Label hypothesis, code-verified, and empirically verified.
  - Trigger independent recheck when the conclusion changes.
- **Reuse scan:**
  - **Name layer:** `evidence-backed claim`, `claim gate`, `claim verification`, `evidence gate` → no existing skill or reference.
  - **Behavior layer:** `counter-hypothesis`, `empirical evidence`, `code-verified`, `acceptance boundary`, `hypothesis`, `evidence` → partial behavior in `systematic-debugging`, `audit-ticket`, `browser-qa`, `review-pr`, and `harden-plan`.
  - **Reference layer:** Existing workflows make evidence local to debugging, ticket audits, UI QA, and reviews; no artifact owns cross-cutting claim maturity or conclusion reversal.
- **Resolved design tree:**
  1. Which claims enter the gate?
  2. Is the final artifact a new cross-cutting skill, a shared reference reached by existing skills, or targeted amendments?
  3. What evidence combination is sufficient for each claim class?
  4. When is a counter-hypothesis mandatory?
  5. What claim-state vocabulary and output shape persist the result?
  6. What constitutes a changed conclusion, and who performs the independent recheck?
  7. How should unavailable empirical evidence affect the claim and downstream action?
  8. What examples, evaluation cases, and acceptance-surface checks prove the artifact works?
- **Decisions:**
  1. **Gate scope:** Govern decision-driving claims: claims that affect a diagnosis, recommendation, mutation, completion verdict, or user decision. Ordinary factual narration stays outside the gate.
  2. **Artifact architecture:** Create one cross-cutting, model-invoked skill that owns the protocol, can trigger autonomously, and can be reached by other workflows.
  3. **Evidence contract:** Require lane-specific paired evidence: a basis plus an acceptance-boundary observation. Examples include code path plus runtime behavior, mutation ledger plus read-back, parser/discovery plus invocation, and source plus direct data check.
  4. **Counter-hypothesis:** Record the strongest plausible alternative before concluding every gated claim.
  5. **Skill name:** Use `verify-claims`, a short verb-led name that states the agent's action.
  6. **Claim record:** Use a structured claim card containing the claim, consequence, counter-hypothesis, basis evidence, boundary evidence, limitations, next action, and one closed state: `hypothesis`, `basis-verified`, `verified`, `contradicted`, or `blocked`.
  7. **Missing evidence:** Apply an evidence ceiling. Without acceptance-boundary evidence, a claim cannot become `verified`; name the missing evidence, keep dependent conclusions provisional, stop irreversible or external actions, and allow reversible work only under an explicit assumption.
  8. **Invocation timing:** Invoke just before presenting or acting on an inference-backed, decision-driving claim, and invoke again when the user challenges it or the conclusion changes.
  9. **Persistence:** Write claim cards into an already-authorized writable ledger, report, or durable issue artifact when one exists; otherwise render the card in the response. Do not create a standalone file or mutate an external artifact for a transient claim.
  10. **Conclusion reversal:** A material change to a recorded or communicated claim's truth state, recommended action, or prior action justification triggers a fresh independent reviewer. Give that reviewer exact raw-source identifiers, the decision scope or query, and the counter-hypothesis; exclude directories or artifacts containing prior conclusions, the original rationale, and prior or proposed values. Gate reliance on the replacement conclusion until the recheck returns.
  11. **Acceptance bar:** Require a layered evaluation suite: repository structural verification; positive and negative fresh-session trigger cases; fresh-agent scenarios covering code, external mutation, configuration and invocation, and data claims; and explicit cases for missing evidence, contradicted claims, and material conclusion reversal.
- **Shared-understanding confirmation:** Confirmed by the user on 12 August 2026. Grill complete.
- **Final artifact:** `skills/verify-claims/`
- **Verification evidence:**
  - Repository structural verifier passed across 19 skills and 51 Markdown files; one pre-existing `git-commit` frontmatter warning remained.
  - Source-skill discovery was proved in isolated project sandboxes before trigger measurement.
  - Fresh-session routing samples covered pre-reliance, autonomous completion claims, challenged claims, bare challenges, material reversals, direct-fact and direct-edit negatives, bug-diagnosis and finish-workflow collisions, and a harmless factual correction. Deterministic negatives were 3/3; challenged-claim samples showed model variance at 2/3 in the final targeted rerun.
  - Code lane: `verified` from exact `calculate_discount` path plus executed public result `10.0`.
  - External-mutation lane: `basis-verified`; successful mutation receipt did not substitute for missing authoritative board read-back.
  - Configuration lane: `contradicted`; registration passed while picker visibility and manual invocation failed.
  - Data reversal lane: `verified`; owner-filtered total recomputed as 12 versus the prior unfiltered 25, then independently reproduced by a blind reviewer given only `query.json`, `final_ledger.csv`, the decision scope, and the counter-hypothesis.
  - The final behavior evaluator parses ten non-empty claim-card fields, binds exact state and next-action semantics, associates tool inputs with returned evidence, checks acceptance-surface observations, and rejects prior or proposed values in blind-review inputs. Replaying the valid four-lane fresh-session stream through the final evaluator passed 4/4; demonstrated fabricated-card and value-leak bypasses failed.
  - A later live rerun was attempted after the last protocol tightening, but the provider returned HTTP 429 for every case. The runner now reports that as `api error 429` rather than accepting the provider's misleading `subtype: success`; the blocked rerun does not replace the valid replayed fresh-session evidence.
  - Three independent finish reviewers converged at zero Critical, Serious, or Moderate findings. Added-comment review found no violations.
  - Standalone `quick_validate.py` did not start because the available Python environment lacks PyYAML; the repository's own structural verifier covered frontmatter, name, fences, pointers, and cross-skill contracts.

### R02 — External-state mutation preflight

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Low-frequency Git, board, and issue mistakes had outsized cost because they changed shared state.
- **Source specification:** Resolve target and ownership; inspect base, head, and dependencies; check published-history status; preview ambiguous splits or grouping; record reversibility and approval.
- **Reuse scan:**
  - `audit-ticket` already requires an exact issue and explicit fate choice, but it lacks ownership checks, dependency inspection, successor preview, reversibility classification, and authoritative read-back.
  - `review-pr` pins a PR URL and head SHA and asks before posting, but it can infer rolling-review restructuring, resolve threads before the new post, and lacks one approval/recovery record across sub-mutations.
  - `fix-pr-review` checks repo and branch and separately asks before checkout, stash, commit, and push, but it does not revalidate thread/head/upstream state immediately before mutation or inspect stacked dependencies.
  - `executing-tickets-with-subagents` locks user decisions and reads back checklist writes, but pushes, PR-body edits, ready-state changes, follow-up grouping, and issue creation do not share a per-mutation preflight contract.
  - `git-commit` is append-only and stages inspected files, while `resolving-merge-conflicts` accounts for both parent intents; neither checks whether history is already published or consumed by dependent branches and PRs.
  - `browser-qa` can mutate shared UI data without a universal environment, ownership, snapshot, restoration, or destructive-submit gate.
  - No project-board mutation or publication/deployment skill exists. `verify-claims` owns the evidence/read-back boundary after a write, not permission to perform it.
- **Architecture hypothesis:** One model-invoked preflight authority plus narrow invocation pointers at existing mutation call sites. A shared reference alone cannot fire for ad-hoc surfaces; targeted amendments alone would duplicate the protocol and leave future tools uncovered.
- **Open design tree:**
  1. Which state classes are in scope: remote/shared state only, published local history, live services, production-like UI data, and off-box copies?
  2. Does the preflight run per task, per mutation category, per approved batch, or per individual write; what invalidates it?
  3. What user language constitutes approval, how narrow is it, and which action classes always require specific confirmation?
  4. Is requester ownership mandatory, policy-specific, or replaceable by verified authority plus an explicit request?
  5. How deeply must bases, heads, stacked PRs, linked issues, release consumers, workflows, and umbrella records be traversed?
  6. What establishes published or consumed history, and when must an append-only correction replace rewrite or deletion?
  7. Which mutations require a user-visible preview, and what must that preview show?
  8. What reversibility vocabulary and recovery evidence gate execution?
  9. When is the preflight record inline versus persisted in an existing ledger?
  10. How do changed guards and partial execution stop or reauthorize the remaining batch?
  11. What extra contract applies to browser-driven shared data, production operations, and service downtime?
  12. Where are the boundaries with R01 claim verification, R03 board calibration, and R05 surface-aware completion?
- **Decisions:**
  1. **Scope:** Cover shared or remote state, published Git history, production-like data, live services, and off-box copies. Exclude isolated worktree changes and unpublished local commits.
  2. **Trigger and invalidation:** Run once immediately before an approved mutation batch. Invalidate the preflight when the target, action, ownership, dependencies, head, publication status, or approval changes. Stop and re-preflight any unexecuted remainder.
  3. **Approval:** Treat a specific task request as approval for ordinary reversible writes within its stated target. Require fresh explicit confirmation for restructuring, compensating-only or irreversible actions, production data, published-history rewrites, and resources outside the normal ownership policy.
  4. **Ownership:** Apply the governing surface's ownership policy. Verified technical write authority alone does not broaden the requested target or override an assignee, author, environment, or resource-owner boundary.
  5. **Dependency and publication depth:** Inspect direct dependencies for ordinary writes and transitive consumers before deletion, closure, base changes, or history rewrites. Prefer append-only corrections whenever state is already published or consumed.
  6. **Preview:** Require a user-visible preview for ambiguous restructuring, high-volume mutations, production operations, ownership expansion, and compensating-only or irreversible changes. Show targets, delta, exclusions, dependencies, blast radius, and recovery path.
  7. **Reversibility:** Use the closed classes `reversible`, `compensating-only`, and `irreversible`. Recovery evidence must match the class before execution.
  8. **Persistence:** Keep a simple preflight inline. Persist multi-step or multi-batch preflights in an existing authorized ledger; do not create or mutate an external artifact merely to store the preflight.
  9. **Partial execution:** A changed guard invalidates approval for the unexecuted remainder. Preserve the landed subset and observed external state before re-preflighting; never restart the whole batch from an assumed zero state.
  10. **Operational lane:** Production-like UI data, production operations, service downtime, and off-box copies require an environment or recipient check, ownership, snapshot or backup where possible, restoration or compensation plan, and distinct confirmation.
  11. **Workflow boundaries:** R02 determines whether an already-authorized batch is ready for execution; it never grants authority. R01 verifies decision-driving claims and post-write read-back, R03 owns board calibration and representative high-volume previews, and R05 owns final surface-aware completion verification.
  12. **Architecture:** Create one model-invoked preflight authority with narrow invocation pointers at existing mutating call sites, rather than duplicating the protocol inside each workflow.
- **Round-one confirmation:** All recommended positions accepted by the user on 12 August 2026.
- **Round-two decisions:**
  13. **Skill name and responsibility:** Name the skill `preflight-mutations`. It prepares or blocks a mutation but never performs the write itself.
  14. **Mutation card:** Emit one card containing the surface and environment, exact action and targets, governing ownership policy, authorization source, current guards, dependencies or consumers, preview and exclusions, reversibility class, recovery plan, invalidators, and post-write read-back plan.
  15. **Preflight verdict:** Use the closed verdicts `ready`, `confirmation-required`, and `blocked`. Any changed guard invalidates `ready`.
  16. **Batch execution record:** Track each item as `pending`, `landed`, `failed`, or `skipped`. On interruption or invalidation, preserve and authoritatively re-read the landed subset before re-preflighting only the remainder.
  17. **Integration pointers:** Add narrow invocation pointers to `audit-ticket`, `review-pr`, `fix-pr-review`, `executing-tickets-with-subagents`, published-history conflict handling, production-like `browser-qa`, and live or off-box backup operations. Leave local-only `git-commit` unchanged.
  18. **Acceptance bar:** Require repository structural checks, positive and negative fresh-session routing cases, and behavioral scenarios for issue splitting, published-history rewrite, production UI data, and partial-batch invalidation. Each scenario must prove exact target resolution, correct confirmation behavior, appropriate dependency and recovery evidence, and a post-write read-back plan.
- **Round-two confirmation:** All recommended positions accepted by the user on 12 August 2026. The design frontier is empty; shared-understanding confirmation remains before implementation.
- **Shared-understanding confirmation:** Confirmed by the user on 12 August 2026. Grill complete.
- **Final artifact:** `skills/preflight-mutations/`
- **Verification evidence:**
  - The repository structural verifier passed across 20 skills and 52 Markdown files; the only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - Four fresh read-only Codex examples covered issue split-and-close, published-history rewrite, production UI data, and partial-batch invalidation. They were used as sampled design evidence; the temporary bespoke evaluator and fixture tree were removed after the user corrected the run for over-testing and over-engineering.
  - The issue lane resolved exact predecessor and successor IDs, another assignee's ownership boundary, direct and transitive consumers, a complete successor preview, compensating recovery, fresh confirmation, and authoritative read-back.
  - The history lane chose `confirmation-required`, classified a consumed rewrite as `compensating-only`, preserved exact-SHA and backup guards, surfaced the append-only correction, traversed direct and transitive consumers, and required lease-guarded recovery and read-back.
  - The production lane required recorded resource-owner authority plus distinct confirmation, preserved the exact account/version/prior plan, classified persistent downstream effects as `compensating-only`, and named restoration, reconciliation, and authoritative read-back.
  - The partial-batch lane retained authoritative `landed` state for `GSM3-301` and `GSM3-302`, limited **Targets** to pending `GSM3-303` and `GSM3-304`, invalidated the old approval after the guard changed, and required fresh confirmation.
  - Nine native Claude routing cases are recorded in `tools/eval/triggers.json`. A live routing attempt was correctly reported as an evaluator error because the provider returned HTTP 429; it was not counted as a routing miss. In fallback Codex behavior-routing probes, all three local/read-only negatives stayed outside the mutation-card workflow and all five shared-state positives stopped before mutation, but the positives did not consistently emit the full card without fixture evidence, so they are not represented as native invocation passes.
  - Independent documentation and specification re-reviews reported zero Critical or Serious findings. The only remaining Moderate was the unavailable native routing run; the provider returned HTTP 429, which the shared trigger runner now reports as an evaluator error rather than a false routing result.

### R03 — Calibrated project-board mutation

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Prevents the archive's most expensive correction and is reusable across project boards.
- **Source specification:** Resolve ownership before writes; ask for estimate unit and 3–5 anchors; preview a representative sample; handle umbrella tickets explicitly; re-fetch and total from the final write ledger.
- **Reuse scan:**
  - `preflight-mutations` already owns exact targets, ownership, authorization, previews, guard invalidation, partial batches, recovery, and authoritative read-back for shared-state writes.
  - No existing skill owns estimate units, representative anchors, umbrella-ticket treatment, or ledger-derived board totals.
  - No board-provider-specific workflow exists in this repository, so provider commands and field schemas should remain outside a reusable core.
- **Architecture hypothesis:** Add a focused calibration skill that prepares a board-write ledger and then hands the exact approved batch to `preflight-mutations`. This keeps numerical calibration separate from shared-state authority without duplicating the mutation gate.
- **Open design tree:**
  1. Should R03 be a focused specialization that hands off to `preflight-mutations`, an expansion of R02, or a standalone end-to-end board workflow? **Resolved:** focused specialization.
  2. When may an existing durable estimate policy replace asking for a unit and 3–5 anchors? **Resolved:** only when a durable policy defines the unit, scale, representative anchors, and applicability to the current board.
  3. What sample, umbrella-ticket, aggregation, and final-total evidence is required before and after writes? **Resolved:** representative preview plus authoritative final read-back.
- **Decisions:**
  1. **Architecture:** Create a focused calibration skill that produces an approved board-write ledger, then hand that exact batch to `preflight-mutations` for shared-state authorization and execution gating.
  2. **Calibration source:** Reuse an existing durable policy only when it defines the estimate unit, scale, representative anchors, and applicability to the current board. Otherwise obtain 3–5 fresh anchors before preparing writes.
  3. **Evidence gate:** Preview 3–5 varied representative items before preparing the batch. Classify every umbrella as directly estimated, excluded, or derived from children without double-counting. After execution, re-fetch every written item and calculate totals only from confirmed final values.
- **Proposed implementation shape:** Create a concise model-invoked `calibrate-board-mutations` skill. It resolves the owner boundary, calibration policy or anchors, representative preview, umbrella treatment, intended batch ledger, and final read-back calculation; it delegates shared-state authorization to `preflight-mutations` and performs no board write itself. Validate with the existing structural verifier and lightweight routing examples only.
- **Shared-understanding confirmation:** Confirmed by the user on 13 August 2026. Grill complete.
- **Final artifact:** `skills/calibrate-board-mutations/`
- **Verification:**
  - The repository structural verifier passed across 21 skills and 53 Markdown files; the only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - Five lightweight routing cases cover multi-item calibration, changed-unit recalibration, partial-batch reconciliation, exact single-value collision with `preflight-mutations`, and read-only exclusion. The trigger catalog parses successfully.
  - Diff and added-comment checks passed. One bounded independent review reported zero Critical or Serious findings.
  - The optional standalone validator could not start because PyYAML is not installed; no dependency was installed because the repository verifier covers the committed skill structure.

### R04 — Review-ledger convergence

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Retains the proven value of independent review without endless review waves.
- **Source specification:** Hash the reviewed diff; store reviewer coverage and disposition; rerun delta plus open findings only; cap convergence at three rounds; convert important remainder to issues.
- **Known overlap to resolve:** `review-pr`, `parallel-review`, and their persisted finding state.
- **Reuse scan:**
  - `review-pr` already persists stable finding IDs and dispositions, compares cached head SHA with the current head, replays an unchanged review, re-reviews only new commits when ancestry is intact, invalidates on rewritten history, and relaxes Moderate/Minor blocking from round 3.
  - `parallel-review` builds a reviewer roster and merges traceable findings, but retains no diff identity, coverage record, finding dispositions, or round history between invocations.
  - `done` repeatedly calls `parallel-review` until Critical and Serious reach zero, with no explicit round cap or unchanged-diff reuse contract.
  - No existing workflow enforces a hard three-round stop or converts important unresolved remainder into approved follow-up work.
- **Initial architecture hypothesis (rejected):** Amend the existing review workflows rather than create another user-facing command. The user instead selected a dedicated convergence skill so all reviewers share one coordinator contract.
- **Open design tree:**
  1. Should convergence amend `review-pr`, `parallel-review`, and `done`, or live in a new standalone skill? **Resolved:** standalone convergence skill.
  2. Is the convergence skill model-invoked by the existing review workflows or manual-only? **Resolved:** automatic shared coordinator.
  3. What exactly identifies an unchanged review scope and invalidates prior evidence? **Resolved:** content hash plus review contract, with affected-area invalidation.
  4. Does the three-round cap apply per unchanged scope, per task, or separately to PR and local review? **Resolved:** three rounds per stable review scope.
  5. Which unresolved findings become follow-up issues, and what approval is required before creating them? **Resolved:** blockers remain; important non-blockers become a proposed follow-up requiring approval before external creation.
- **Decisions:**
  1. **Architecture:** Create a dedicated convergence skill that owns the shared ledger and convergence decision rather than independently extending each review workflow.
  2. **Invocation:** Make `converge-reviews` model-invoked. `review-pr`, `parallel-review`, and `done` hand every completed review round to it; users may also invoke it directly.
  3. **Scope identity:** Key reusable evidence by reviewed diff hash, base/head, scope paths, reviewer roster and lenses, and originating request. Reuse unchanged coverage; invalidate and re-review only the affected portion when that contract changes.
  4. **Round cap:** Allow at most three review/fix rounds per stable review scope. A material change resets only its affected portion; cosmetic, generated, or unrelated changes do not reset the counter.
  5. **Cap disposition:** Keep Critical and Serious findings blocking after round three. Convert worthwhile Moderate and Minor remainder into a proposed follow-up list. Creating external issues requires user approval and `preflight-mutations`; dismissed noise remains closed in the ledger.
- **Proposed implementation shape:** Create a concise model-invoked `converge-reviews` skill that owns a common ledger contract and returns `continue`, `converged`, `blocked-at-cap`, or `follow-up-proposed`. Add narrow handoffs from `review-pr`, `parallel-review`, and `done`; reuse `review-pr`'s existing finding state rather than replacing it. Validate structurally plus lightweight routing and contract inspection only.
- **Shared-understanding confirmation:** Confirmed by the user on 13 August 2026. Grill complete.
- **Final artifact:** `skills/converge-reviews/`, with narrow handoffs from `review-pr`, `parallel-review`, and `done`.
- **Verification:**
  - The repository structural verifier passed across 22 skills and 54 Markdown files; the only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - Five lightweight routing cases cover repeated-round reconciliation, the round-three cap, affected-coverage reuse, and first-review collisions with `parallel-review` and `review-pr`. The trigger catalog parses successfully.
  - Diff and added-comment checks passed. One bounded review found two Serious contract gaps: caller-specific `regression` state was not normalized as open, and the cap lacked a blocker-fix verification path.
  - The affected-area repair maps all caller-specific open states to blocking semantics and allows exactly one targeted blocker-closure check without a new-finding sweep or fourth review round. The affected-area recheck reported zero Critical or Serious findings.

### R05 — Surface-aware done

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Mandatory verification is valuable, but code checks do not validate board writes, global config, or publication.
- **Source specification:** Route to code, docs, global config, external metadata, or publication lane; verify the actual acceptance surface; avoid unrelated repository checks; always report verified versus assumed.
- **Known overlap to resolve:** The mandatory `done` skill.
- **Decisions / final artifact / verification:** Pending.

### R06 — Bounded unattended orchestrator

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Addresses duplicate agents, capacity failures, progress nudges, and lost state in overnight work.
- **Source specification:** One owner per task; fixed worker pool; one retry on capacity failure; material-only updates; durable morning handoff ledger.
- **Known overlap to resolve:** `executing-tickets-with-subagents` and its ledger contract.
- **Decisions / final artifact / verification:** Pending.

### R07 — Claude ↔ Codex setup sync

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Makes custom workflow migration behavior-preserving and testable.
- **Source specification:** Classify exact copy, adaptation, and unsupported behavior; treat custom slash workflows as portable; preserve backups; verify parsing, discovery, picker visibility, and manual invocation separately.
- **Decisions / final artifact / verification:** Pending.

### R08 — Structured decision ledger

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Structured choices were frequent, and several sessions asked to show options again after mistaken selection.
- **Source specification:** Echo the effective decision; allow recap and undo; persist rationale and dependencies; confirm before irreversible action.
- **Known overlap to resolve:** `grill-me` file write-back and `harden-plan` resolution state.
- **Decisions / final artifact / verification:** Pending.

### R09 — Ticket evidence preservation

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Repeated extraction and split workflows lost screenshots, author context, or exact source evidence.
- **Source specification:** Treat screenshots as source of truth; preserve author, text, and image references; link predecessor and successor tickets; reread the final ticket; post investigation back to the durable issue.
- **Known overlap to resolve:** `audit-ticket` and `executing-tickets-with-subagents` intake.
- **Decisions / final artifact / verification:** Pending.

### R10 — Artifact lifecycle manager

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Artifacts are valuable but proliferated, competed, or lost unique evidence during consolidation.
- **Source specification:** Maintain one canonical URL; track sources and superseded artifacts; deduplicate without discarding unique findings; verify links and duplicate status at closeout.
- **Decisions / final artifact / verification:** Pending.

### R11 — Merge-readiness evidence card

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Directly answers recurring “are we good?”, “what is left?”, and “no regression?” loops.
- **Source specification:** Map each request item to implementation; list tests, browser, database, CI, and review evidence; separate verified, assumed, deferred, and pending; state the exact next action.
- **Known overlap to resolve:** `done` correctness accounting and completion reporting.
- **Decisions / final artifact / verification:** Pending.

### R12 — Non-interactive tooling canary

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** A package-manager firewall wrapper broke non-interactive pnpm use and forced development workflows to bypass the workspace runner.
- **Source specification:** Test interactive and non-interactive shells; exercise development, test, and workspace-build commands; verify dependent package outputs; document intentional bypasses and their cost.
- **Decisions / final artifact / verification:** Pending.

### R13 — Material-state progress updates

- **Priority:** P1
- **Proposed destination:** Global rules
- **Status:** `pending`
- **Rationale:** Universal, short, and cheap to enforce on every long-running task.
- **Source specification:** Report completed, active, blocked, and next; update only on a material state, ETA, decision, or blocker change.
- **Decisions / final artifact / verification:** Pending.

### R14 — Evidence reuse and ownership

- **Priority:** P1
- **Proposed destination:** Global rules
- **Status:** `pending`
- **Rationale:** Universal guardrail against redundant subagents and reviewer churn.
- **Source specification:** Never assign the same scope to two agents; treat completed reviewer output as valid until the diff changes.
- **Decisions / final artifact / verification:** Pending.

### R15 — GSM3 operating facts

- **Priority:** P0
- **Proposed destination:** Project rules
- **Status:** `pending`
- **Rationale:** Board fields, estimate scale, runner policy, database fingerprints, module names, and migration permissions are repository-specific.
- **Source specification:** Agent-assisted estimate anchors; owner-only board mutation; Blacksmith runner policy; database target preflight; module and release field vocabulary.
- **Decisions / final artifact / verification:** Pending; requires the GSM3 repository's actual rule source and acceptance surface.

### R16 — Spanical landing conventions

- **Priority:** P1
- **Proposed destination:** Project rules
- **Status:** `pending`
- **Rationale:** Stacked PR and Drizzle conventions should not burden unrelated projects.
- **Source specification:** Main integration base; bottom-up stacked merges; exact-SHA lease checks; Drizzle migration convention; repository config over repeated CLI flags.
- **Decisions / final artifact / verification:** Pending; requires the Spanical repository's actual rule source and acceptance surface.

### R17 — Fileseye skill-change canary

- **Priority:** P1
- **Proposed destination:** Project rules
- **Status:** `pending`
- **Rationale:** A large prerequisite rewrite broke the skill it intended to improve, and review rounds expanded without convergence.
- **Source specification:** Snapshot current behavior; run representative fixtures before and after; bound review rounds; block merge on behavior regression; preserve named user workflows.
- **Decisions / final artifact / verification:** Pending; requires the Fileseye repository's actual rule source and acceptance surface.

### R18 — Fact-bound personal drafting

- **Priority:** P2
- **Proposed destination:** Decision log
- **Status:** `pending`
- **Rationale:** A personal-content draft invented motivations and public positioning, but this is narrow to personal copy work.
- **Source specification:** Separate known facts from inferred narrative; ask before inventing motivations or disclosure intent; keep private experiments private unless explicitly authorized.
- **Decisions / final artifact / verification:** Pending.

## Change log

### 12 August 2026 — Ledger initialized

- Preserved the retrospective's corpus, method, correction patterns, strengths, and all 18 recommendations in one canonical file.
- Established a closed status vocabulary, per-item gates, a sole active item, and an imperative next action.
- Completed a repository overlap scan for R01. Existing skills contain domain-specific evidence workflows, but no artifact owns claim maturity across domains.
- Opened R01's design tree; no user decisions have been recorded yet.
- Marked R01 blocked after three consecutive goal turns without the required Q1 scope decision. No implementation was started from an unconfirmed assumption.
- Recorded R01 decision 1: the gate covers decision-driving claims. Restored R01 to `grilling` and opened the next three independent branches.
- Recorded R01 decisions 2–4: a model-invoked cross-cutting skill, paired lane-specific evidence, and a mandatory strongest plausible counter-hypothesis. Choosing a standalone skill opened a naming and trigger-language branch.
- Recorded R01 decisions 5–7: name the skill `verify-claims`, emit structured claim cards with a closed state vocabulary, and cap claims when boundary evidence is unavailable.
- Recorded R01 decisions 8–10: invoke just before reliance, persist into the existing durable artifact when present, and independently recheck every material conclusion reversal using raw evidence.
- Recorded R01 decision 11: require layered structural, trigger, lane-behavior, missing-evidence, contradiction, and reversal evaluation. The design frontier is empty; implementation awaits explicit shared-understanding confirmation.
- User confirmed the complete R01 decision record. Marked the grill complete and moved R01 to `implementing`.
- Implemented `skills/verify-claims/`, documented it in `README.md`, added ten trigger cases, enabled isolated source-skill trigger tests, and added four behavioral fixture lanes. Moved R01 to `verifying` after every behavioral lane produced the intended claim state and action boundary.
- Hardened R01 through three finish-review rounds: aligned unavailable-evidence states, restricted persistence to authorized artifacts, made blind reversal inputs source-exact, separated evaluator errors from routing outcomes, and replaced prose-only checks with structured card, tool-result, state, action, and leakage assertions.
- Closed R01 after the final evaluator replay passed all four fresh-session lanes and three independent reviewers reported zero Critical, Serious, or Moderate findings. Recorded the provider-429 rerun limitation explicitly. Advanced R02 to `researching`.
- Completed R02's repository overlap scan. Existing workflows contain useful local guards but no cross-surface preflight authority; advanced R02 to `grilling` with a twelve-branch design tree.
- Recorded the user's acceptance of all recommended R02 round-one positions: scope, batch invalidation, approval, ownership, dependency depth, publication policy, preview, reversibility, persistence, partial execution, operational safeguards, workflow boundaries, and the central-skill architecture.
- Recorded the user's acceptance of all recommended R02 round-two positions: `preflight-mutations`, the mutation-card schema, three verdicts, batch-item states, seven integration surfaces, exclusion of local-only commits, and the layered acceptance suite. The design frontier is now empty pending explicit shared-understanding confirmation.
- User confirmed the complete R02 decision record. Marked the grill complete and moved R02 to `implementing` without reopening settled design choices.

### 13 August 2026 — R02 implementation and verification

- Implemented `skills/preflight-mutations/`, registered it in the README, and added narrow pre-write handoffs to the seven confirmed mutation-owning workflows while leaving local-only `git-commit` unchanged.
- Added nine routing cases and exercised four read-only behavior examples. Hardened the contract around consumed-history recovery, exact-SHA leases, captured production prior values, self-contained next actions, and partial-batch provenance.
- The user corrected the run for over-testing and over-engineering. Removed the per-skill evaluator and fixture tree, retained the reusable structural verifier and trigger catalog, and added the proportional-delivery rule to this ledger.
- Closed R02 after proportional structural, syntax, JSON, diff, and sampled behavior checks. Advanced R03 to `grilling` after confirming that calibration is the missing behavior and shared-state authority already belongs to `preflight-mutations`.
- Recorded R03 decision 1: board calibration is a focused specialization that hands its exact batch to `preflight-mutations` rather than expanding or duplicating the shared-state gate.
- Recorded R03 decision 2: a durable estimate policy replaces fresh anchors only when it completely defines the unit, scale, representative anchors, and current-board applicability.
- Recorded R03 decision 3: preview 3–5 varied items, classify every umbrella without double-counting, and derive final totals only from authoritative read-back of confirmed writes. The grill frontier is empty pending shared-understanding confirmation.
- User confirmed the complete R03 design. Implemented the concise `calibrate-board-mutations` workflow and moved R03 to `implementing`.
- Closed R03 after proportional structural, routing-data, diff, and one-pass Critical/Serious review checks. Advanced R04 to `researching`.
- Completed the R04 overlap scan. `review-pr` already implements most convergence machinery, while `parallel-review` and `done` lack durable scope and round state; advanced R04 to `grilling` without assuming a new skill is needed.
- Recorded R04 decision 1: create a dedicated convergence skill. Added the dependent invocation/coordination decision to the design frontier.
- Recorded R04 decision 2: `converge-reviews` is an automatic shared coordinator invoked after each `review-pr`, `parallel-review`, and `done` review round.
- Recorded R04 decision 3: reuse evidence by content hash plus review contract and invalidate only the affected portion when the diff, scope, roster, lens, or originating request changes.
- Recorded R04 decision 4: cap review/fix convergence at three rounds per stable scope, resetting only a materially changed affected portion.
- Recorded R04 decision 5: Critical/Serious remain blocking at the cap; worthwhile Moderate/Minor remainder becomes a proposed follow-up whose external creation requires approval and `preflight-mutations`. The grill frontier is empty pending confirmation.
- User confirmed the complete R04 design. Implemented the concise `converge-reviews` coordinator, preserved `review-pr`'s finding state as authoritative, and added the three agreed handoffs.
- Closed R04 after proportional structural, routing-data, diff, and bounded review checks. The only review findings were fixed and the affected-area recheck reported zero Critical or Serious issues. Advanced R05 to `researching`.
