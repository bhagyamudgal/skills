# Agent Session Recommendation Ledger

This is the authoritative source and recovery map for turning the 12 August 2026 Agent Session Retrospective into durable agent behavior. Resume by reading this file and executing `NEXT ACTION`; conversation memory and summaries are not run state.

## Run state

- **Objective:** Process every recommendation in source order. For each item, finish a `grill-me` design tree, obtain explicit confirmation of shared understanding, write the agreed artifact with `writing-for-agents`, verify it at its acceptance surface, and update this ledger before advancing.
- **Current item:** `R15 — GSM3 operating facts`
- **NEXT ACTION:** Locate the GSM3 repository and its authoritative project-rule source before opening the R15 grill.
- **Progress:** 12 complete; 2 declined; 1 researching; 3 pending.
- **Canonical artifact:** `docs/agent_session_recommendations.md`
- **Source artifact:** Agent Session Retrospective, local research artifact dated 12 August 2026, served at `http://127.0.0.1:4173/` when captured.
- **Last updated:** 14 August 2026

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
| R05 | P0 | Surface-aware done | Skill | `complete` | `skills/done/` | Complete |
| R06 | P1 | Bounded unattended orchestrator | Skill | `complete` | `skills/executing-tickets-with-subagents/` | Complete |
| R07 | P1 | Claude ↔ Codex setup sync | Skill | `complete` | `skills/sync-agent-setups/` | Complete |
| R08 | P1 | Structured decision ledger | Skill | `declined` | Decision recorded | Declined as disproportionate |
| R09 | P1 | Ticket evidence preservation | Skill | `complete` | `skills/audit-ticket/references/ticket-evidence.md` | Complete |
| R10 | P1 | Artifact lifecycle manager | Skill | `complete` | `skills/manage-report-lifecycle/` | Complete |
| R11 | P1 | Merge-readiness evidence card | Skill | `complete` | `skills/done/` and `skills/file-pr/` | Complete |
| R12 | P1 | Non-interactive tooling canary | Skill | `declined` | Decision recorded | Declined as disproportionate |
| R13 | P1 | Material-state progress updates | Global rules | `complete` | `~/.claude/CLAUDE.md` and `reference/CLAUDE.md` | Complete |
| R14 | P1 | Evidence reuse and ownership | Global rules | `complete` | `~/.claude/CLAUDE.md` and `reference/CLAUDE.md` | Complete |
| R15 | P0 | GSM3 operating facts | Project rules | `researching` | TBD | Locate project authority |
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
- **Status:** `complete`
- **Rationale:** Mandatory verification is valuable, but code checks do not validate board writes, global config, or publication.
- **Source specification:** Route to code, docs, global config, external metadata, or publication lane; verify the actual acceptance surface; avoid unrelated repository checks; always report verified versus assumed.
- **Known overlap to resolve:** The mandatory `done` skill.
- **Reuse scan:**
  - `done` is already the mandatory completion entry point, but it always assumes a code change: workspace type-check, local diff review, simplification, correctness, report, and commit.
  - `browser-qa` verifies UI flows at the browser, including screenshots, network, and console evidence.
  - `verify-claims` already defines paired evidence and evidence ceilings for decision-driving completion claims.
  - `preflight-mutations` owns authoritative read-back plans for shared-state writes; `calibrate-board-mutations` owns confirmed board totals.
  - Global configuration, skill discovery/manual invocation, documentation rendering/links, external metadata, and publication have no completion router. Running repository checks against these surfaces can pass while the user-facing outcome remains unverified.
- **Architecture hypothesis:** Deepen the mandatory `done` skill into a surface router rather than add a second completion command. Delegate lane-specific checks to existing skills where they exist and keep the universal verified/assumed report in `done`.
- **Open design tree:**
  1. Should R05 deepen `done`, create a separate surface-verification skill, or add a shared reference behind `done`? **Resolved:** deepen `done`.
  2. Should the agent infer acceptance surfaces from the request and diff, or require the user to declare them? **Resolved:** agent infers and shows lanes; user may override.
  3. Which lanes and minimum evidence belong in the routing table? **Resolved:** six practical lanes.
  4. What completion states and reporting fields are required when a surface is unavailable or intentionally deferred? **Resolved:** per-lane states with an evidence ceiling.
- **Decisions:**
  1. **Architecture:** Deepen the mandatory `done` skill into the acceptance-surface router. Preserve one completion command and delegate lane-specific checks rather than creating a competing completion workflow.
  2. **Surface selection:** Infer acceptance surfaces from the originating request, changed artifacts, and external actions. Show the selected lanes before verification and allow the user to correct them; do not require routine declaration.
  3. **Lane table:** Route across six practical lanes: code, UI, documentation, global configuration or skills, external metadata or data, and publication or deployment. Minimum evidence is respectively targeted/full checks plus review; affected browser flow; rendered final artifact plus links; parse/discovery/picker/manual invocation as applicable; authoritative re-fetch and comparison; and inspection of the published consumer or live target.
  4. **Completion states:** Assign each lane `verified`, `assumed`, `deferred`, `blocked`, or `not-applicable`. Overall completion is `verified` only when every required lane is verified; otherwise report the evidence ceiling, exact gap, and next action without claiming full completion.
- **Proposed implementation shape:** Rewrite the existing `done` workflow around surface selection and a six-lane evidence card, while keeping code-only checks conditional and preserving `converge-reviews` for code review rounds. Reuse `browser-qa`, `verify-claims`, and authoritative read-back from mutation workflows where relevant. Update the README description and lightweight routing cases; add no new skill or evaluator.
- **Shared-understanding confirmation:** Confirmed by the user on 13 August 2026. Grill complete.
- **Final artifact:** `skills/done/`, with its README description, lightweight routing cases, and `reference/CLAUDE.md` completion rule updated in place. No competing skill or evaluator was added.
- **Verification:**
  - The repository structural verifier passed across 22 skills and 54 Markdown files; the only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - The trigger catalog parses successfully with 48 unique cases. Three focused cases cover explicit code completion, combined documentation/skill completion, and the `browser-qa` evidence-production collision; no live provider eval ran.
  - Contract inspection confirmed all six lanes, all five states, the conditional code pipeline, delegated boundary owners, and the overall evidence ceiling. Diff and added-comment checks passed.
  - Foundation's Markdown parser accepted all four changed Markdown documents. The changed hunks add no links, assets, or navigation paths requiring separate traversal.
  - A fresh-agent acceptance review confirmed the six-lane routing, conditional code checks, and evidence ceiling, then reported zero Critical or Serious findings. Its affected-area recheck confirmed the ledger statuses are aligned.

### R06 — Bounded unattended orchestrator

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Addresses duplicate agents, capacity failures, progress nudges, and lost state in overnight work.
- **Source specification:** One owner per task; fixed worker pool; one retry on capacity failure; material-only updates; durable morning handoff ledger.
- **Known overlap to resolve:** `executing-tickets-with-subagents` and its ledger contract.
- **Reuse scan:**
  - `executing-tickets-with-subagents` already makes main an orchestrator, runs one implementation wave per task, requires self-contained dispatches, and persists a zero-context ledger with per-task status, commit SHAs, standing rules, artifacts, deferred findings, and an imperative next action.
  - Its current trigger is limited to bundled GitHub tickets. It has no fixed worker-pool declaration, capacity-specific retry bound, material-only update rule, or morning handoff view.
  - Its wedged-agent rule replaces an agent without a retry ceiling. Its reviewers intentionally inspect the same task through distinct lenses, so “one owner” must distinguish the sole mutation owner from independent read-only review.
  - `review-pr` batch mode already demonstrates unattended continuation and end-of-run pending decisions, but owns PR review rather than general task execution.
  - The global unattended rule grants continued execution across the task list, requires one subagent per task and a morning summary, and retains hard authority boundaries. It should remain a short trigger and authority contract rather than duplicate scheduler mechanics.
- **Architecture hypothesis:** Deepen `executing-tickets-with-subagents` with an unattended branch and a disclosed scheduler reference. Reuse its ledger as the single source of run state, widen its model trigger to explicit unattended delegation, and keep the global rule as the short invocation and authority boundary.
- **Open design tree:**
  1. Should R06 deepen `executing-tickets-with-subagents`, create a separate unattended orchestrator, or remain only a global rule? **Resolved:** deepen the existing skill with an unattended branch and disclosed scheduler reference.
  2. Should the unattended branch fire on any explicit away/keep-going delegation, or only when a minimum task count is present? **Resolved:** any explicit away/keep-going delegation; a single task uses one worker.
  3. How should the fixed worker pool and one-owner rule be defined without preventing independent review? **Resolved:** reserve main for orchestration and fix the pool at kickoff to at most three available workers; each task has one mutation owner while independent read-only reviewers remain allowed.
  4. After the pool contract is settled, what happens after the single capacity retry fails? **Resolved:** retry once after the next worker-slot state change; after a second capacity failure, block that task for the run and continue other runnable work.
  5. After scheduler behavior is settled, which transitions deserve user-visible updates and what exact morning handoff must survive compaction? **Resolved:** persist every task transition in the existing ledger, surface only material transitions to the user, and maintain a fixed morning-handoff section in that ledger.
- **Decisions:**
  1. **Architecture:** Deepen `executing-tickets-with-subagents` with an unattended branch and disclosed scheduler reference. Keep its ledger as the sole run-state authority and leave the global rule as the short activation and authority contract.
  2. **Activation:** Enter the unattended branch whenever the user explicitly says they are stepping away and asks the agent to continue. Do not impose a task-count threshold; one task uses one worker and multiple runnable tasks share the fixed pool.
  3. **Pool and ownership:** Reserve main for orchestration and record a kickoff-fixed pool of up to three currently available workers. Do not expand it mid-run. Assign exactly one mutation owner to each task; distinct read-only reviewers may inspect that owner's output without becoming competing owners.
  4. **Capacity failure:** A capacity rejection receives exactly one retry after the next worker-slot state change. A second capacity rejection marks that task `blocked` for the current run; record both attempts and continue every other runnable task. Do not nudge, spin, or open additional capacity retries.
  5. **Updates and handoff:** Keep the existing ledger as the sole durable state. Update it after every task transition, but send user-facing progress only at kickoff, task completion, a new blocker or authority boundary, a materially changed plan, or final handoff. Maintain a morning section containing completed work and verification, active owners, blocked tasks and retry evidence, pending decisions, uncommitted work, opened PRs, and the exact next action.
- **Proposed implementation shape:** Add an explicit unattended branch to `executing-tickets-with-subagents` and disclose its scheduling mechanics in one focused reference loaded only on that branch. Widen the skill description to explicit away/keep-going delegation, add the minimum README and routing updates, and shorten the global unattended rule to point to this skill while retaining its authority limits. Add no evaluator or second orchestrator skill.
- **Shared-understanding confirmation:** Confirmed by the user on 13 August 2026. Grill complete.
- **Final artifact:** `skills/executing-tickets-with-subagents/`, including `references/unattended-scheduler.md`, with its README description, two lightweight routing cases, and the global unattended pointer in `reference/CLAUDE.md` updated in place. No second orchestrator skill or evaluator was added.
- **Verification:**
  - The repository structural verifier passed across 22 skills and 55 Markdown files; the only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - The trigger catalog parses successfully with 50 unique cases. Two focused cases cover explicit unattended delegation with one task and with a multi-task list; no live provider evaluator was added or run.
  - Foundation's Markdown parser accepted all five changed Markdown documents. Diff whitespace validation passed.
  - One bounded acceptance review found four Serious contract gaps: a non-portable reference pointer, zero-slot kickoff deadlock, owner assignment before dispatch success, and an implicit global commit/PR gate. The repair uses the runtime skill path, per-task two-attempt pool initialization, ownerless capacity waits, and a self-contained scoped-diff/verified-check/user-owned-branch authority boundary.
  - The affected-area recheck found one remaining Serious gap: a second zero-slot result globally blocked unrelated runnable tasks. The repair now binds initialization attempts and blocking to one selected task, leaves the pool unset, and lets each remaining runnable task enter its own bounded capacity path. The final exact-line recheck reported zero Critical and zero Serious findings.

### R07 — Claude ↔ Codex setup sync

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Makes custom workflow migration behavior-preserving and testable.
- **Source specification:** Classify exact copy, adaptation, and unsupported behavior; treat custom slash workflows as portable; preserve backups; verify parsing, discovery, picker visibility, and manual invocation separately.
- **Reuse scan:**
  - No existing skill owns Claude ↔ Codex setup inventory, classification, backup, reconciliation, or end-to-end acceptance.
  - Portable skills already converge on `~/.agents/skills`: 65 Claude and 61 Codex entries are symlinks into that shared store. The visible sets have drifted: Claude has shared skills absent from Codex, while Codex also carries platform-system skills and several Claude-sourced exceptions.
  - Claude has two custom slash-command files, `rams.md` and `web-interface-guidelines.md`; no `~/.codex/prompts` directory or equivalent local prompt files were found. Their behavior is portable agent instruction, even though their current packaging is Claude-specific.
  - Backup fragments exist for Claude settings and prior Codex migrations, but there is no per-run backup manifest or restoration map for a setup sync.
  - `done` and `verify-claims` define the needed acceptance boundaries—parse, registration/discovery, picker visibility, manual invocation, and actual consumer behavior—but neither performs migration or reconciliation.
- **Architecture hypothesis:** Add one dedicated user-invoked setup-sync skill. It should inventory Claude Code before transforming, classify each target artifact as exact copy, adaptation, or unsupported, propagate only from Claude Code to other agents, and hand final acceptance to `done`/`verify-claims`.
- **Open design tree:**
  1. Should R07 create a dedicated setup-sync skill, remain a global rule, or be folded into `done`? **Resolved:** create a dedicated user-invoked `sync-agent-setups` skill with automatic/model invocation disabled.
  2. Should one platform be globally authoritative, or should a manifest declare the canonical source and classification per artifact? **Resolved:** Claude Code is authoritative for every other agent; sync direction is outward from Claude Code.
  3. Which setup surfaces belong in scope: user-authored behavior only, or also credentials, history, caches, and platform-managed state? **Resolved:** sync Claude-authored global rules, skills, custom slash workflows, hooks, and non-secret behavioral settings; exclude credentials, histories, caches, telemetry, and platform-managed content.
  4. After authority and scope are settled, how should conflicts, backups, and rollback work? **Resolved:** dry-run manifest first; timestamped path-and-checksum backup before writes; exact-copy drift may be replaced, adaptations carry provenance, unsupported items remain untouched, and ambiguous collisions block only their item.
  5. After packaging rules are settled, when should a custom slash workflow be copied exactly, adapted into a skill, or marked unsupported? **Resolved:** presume behavior portable; exact copy when format and semantics match, adaptation when packaging/tools/invocation differ but behavior survives, and unsupported only when a required capability cannot be reproduced.
  6. What exact evidence is required at parsing, discovery, picker, and manual-invocation boundaries before parity can be claimed? **Resolved:** parse every write, compare full discovery to the manifest, verify picker visibility for every changed user-invoked entry where supported, manually invoke every changed custom workflow/adaptation, and sample bulk exact-copy skills; unavailable surfaces prevent a full-parity claim.
  7. Should an invocation target every detected non-Claude agent automatically, or preview detected targets and let the user select the write set? **Resolved:** inventory and preview every detected target, then require explicit target selection or confirmation before writes.
  8. What happens to downstream-only user-authored artifacts that have no Claude source? **Resolved:** report them as orphaned downstream drift; do not delete or import automatically, and require a separate decision for either action.
  9. Should exact-copy targets share Claude's physical file through symlinks, or receive generated copies that can drift without mutating the source of truth? **Resolved:** keep symlinks to Claude's resolved source and accept shared physical mutation as a deliberate tradeoff.
- **Decisions:**
  1. **Authority and direction:** Claude Code is the source of truth for all other agents. Sync is one-way from Claude Code outward. A downstream agent's local difference is drift to classify or replace, never a candidate source to promote automatically. The manifest records target classification and provenance, not competing authority.
  2. **Invocation:** Package the workflow as a dedicated `sync-agent-setups` skill with `disable-model-invocation: true`. Only explicit user invocation may start inventory, backup, adaptation, or writes; drift detection and other skills never trigger it automatically.
  3. **Scope:** Propagate Claude-authored global rules, skills, custom slash workflows, hooks, and non-secret behavioral settings. Credentials, conversation histories, caches, telemetry, and platform-managed system files are outside the sync inventory and mutation authority.
  4. **Preview, backup, and collision handling:** Generate a dry-run manifest before mutation. Before the first write, create a timestamped backup that preserves every affected path and checksum. Replace classified exact-copy drift; generate adaptations with source/target provenance in the manifest; leave unsupported items untouched. An ambiguous or unclassified collision blocks that item while independent items continue.
  5. **Workflow portability:** Treat Claude custom slash-workflow behavior as portable by default. Classify `exact copy` only when the target accepts the same format and semantics, `adaptation` when behavior survives through different packaging, variables, tools, or invocation syntax, and `unsupported` only when the target lacks a required capability. Preserve the authoritative Claude command unchanged.
  6. **Acceptance evidence:** Verify each target platform independently. Parse every written artifact and compare the complete discovered name set with the manifest. Check picker visibility for every changed user-invoked entry when the target exposes a picker. Manually invoke every changed custom workflow and every generated adaptation; for bulk exact-copy skills, manually invoke a representative sample while parsing and discovering the full set. Label unavailable surfaces explicitly and do not claim full parity for that target. Use `done` for the final evidence card and `verify-claims` if the parity conclusion materially changes.
  7. **Target authorization:** Inventory and preview all detected non-Claude agents, then require the user to select or confirm the targets included in the write set. Detection alone authorizes no mutation; one confirmed invocation may cover all selected targets.
  8. **Downstream-only artifacts:** Classify user-authored content with no Claude source as `orphaned downstream drift`. Preserve it by default. Deletion requires a separate explicit choice after backup; promotion into Claude requires a separate authorship decision because it changes the source of truth.
  9. **Exact-copy storage:** Keep exact-copy targets as symlinks to the authoritative Claude-resolved source. The manifest records the Claude-visible source, resolved physical path, link target, and checksum. This preserves the current shared-store behavior; Claude authority is procedural rather than filesystem isolation, so an edit through a downstream symlink changes the same shared content. Backups preserve both link metadata and resolved content before link replacement.
- **Proposed implementation shape:** Create one user-invoked `sync-agent-setups` skill with model invocation disabled. Keep the workflow spine in `SKILL.md` and disclose the dry-run manifest, backup, classification, target-confirmation, write, and acceptance record shape in one direct reference if needed for legibility. Integrate `preflight-mutations` immediately before confirmed local setup writes and `done`/`verify-claims` at the target acceptance boundary. Add README registration and lightweight manual-invocation metadata; add no bespoke evaluator and do not perform an actual setup sync while building the skill.
- **Grill status:** Complete. The user confirmed the shared understanding on 14 August 2026.
- **Final artifact:** `skills/sync-agent-setups/`, registered in `README.md`. The skill is manual-only in both skill frontmatter and its OpenAI interface policy; it uses one in-file workflow, no extra reference, no evaluator, and performs no setup sync during construction.
- **Verification:**
  - The repository verifier passed across 24 skills and 57 Markdown files; the only warning is the pre-existing ignored `license` key in `git-commit` frontmatter. The system quick validator was unavailable because its Python environment lacks PyYAML, so the repo-native verifier and a direct YAML parse covered the packaging surface.
  - Frontmatter and OpenAI metadata both disable implicit invocation, the default prompt explicitly names `$sync-agent-setups`, and the skill is registered in the README catalogue and usage list. All changed Markdown parsed and diff whitespace validation passed.
  - A fresh explicit `$sync-agent-setups` invocation loaded the manual skill and remained read-only. It honored exclusions while identifying Claude sources plus concrete Codex, Cursor, Gemini CLI, Zed, and GitHub Copilot targets. The bounded check was stopped before manifest synthesis; no setup mutation, backup, or preflight occurred.
  - The first bounded review found two Serious ordering gaps: non-ready items could poison the preflight batch, and adaptation bytes were not fixed before confirmation. The repair preflights only independently ready items and stages/checksums exact adaptation bytes before confirmation. The affected-area recheck reported zero Critical and zero Serious findings.
  - No live setup sync ran, as required by the confirmed construction scope.

### R08 — Structured decision ledger

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `declined`
- **Rationale:** Structured choices were frequent, and several sessions asked to show options again after mistaken selection.
- **Source specification:** Echo the effective decision; allow recap and undo; persist rationale and dependencies; confirm before irreversible action.
- **Known overlap to resolve:** `grill-me` file write-back and `harden-plan` resolution state.
- **Reuse scan:**
  - `grill-me` enumerates decisions, asks one question at a time, detects contradictions, and appends final numbered answers to a passed file. It does not persist after each answer, store rationale/dependencies, expose history, or define recap/undo.
  - `grilling` models a dependency-aware design tree and recomputes the frontier, but its state lives in conversation unless the caller maintains a separate ledger.
  - `harden-plan` distinguishes accepted, dismissed-with-rationale, skipped, and self-healed findings and can write accepted additions into a plan. Those arrays are run-local, its write-back is final-only, and later corrections cannot identify or supersede the effective decision.
  - `review-pr` has a durable lifecycle with reasons and dependency invalidation, but its finding schema is PR-specific and too heavy for ordinary human choices.
  - `preflight-mutations` confirms irreversible or shared-state actions, but it consumes authorization; it does not own the earlier decision history or make mistaken selections undoable.
- **Architecture hypothesis:** Add a small shared decision-lifecycle coordinator rather than another grilling interface. `grill-me`, `grilling`, `harden-plan`, and irreversible-action workflows can reuse one effective-decision record while keeping their existing question formats.
- **Open design tree:**
  1. Should R08 create a dedicated shared decision-lifecycle skill, deepen only `grill-me`, or add a plain shared reference used by existing skills?
  2. Should the coordinator invoke automatically whenever a workflow presents structured choices, or only when a durable artifact exists or the user explicitly asks for recap/undo?
  3. Where should decision state live when the caller has a plan/ledger file, and where should it live when no durable artifact exists?
  4. After identity and storage are settled, what fields and statuses define the effective decision and its history?
  5. How should recap, undo, replacement, and dependency invalidation change downstream decisions?
  6. What confirmation gate must irreversible actions apply to the current effective decisions?
- **Decision:** Declined by the user on 14 August 2026 after the overlap scan. A shared coordinator would add a new state machine and invocation contract across workflows that already preserve the useful parts locally: `grill-me` echoes final decisions, `harden-plan` records accepted/dismissed/skipped rationale, and `preflight-mutations` reconfirms consequential actions. Keep those mechanisms and revisit only if concrete recurrence shows that recap or undo is still being lost.
- **Final artifact:** This decision record; no skill, shared reference, global rule, or workflow integration was added.

### R09 — Ticket evidence preservation

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Repeated extraction and split workflows lost screenshots, author context, or exact source evidence.
- **Source specification:** Treat screenshots as source of truth; preserve author, text, and image references; link predecessor and successor tickets; reread the final ticket; post investigation back to the durable issue.
- **Known overlap to resolve:** `audit-ticket` and `executing-tickets-with-subagents` intake.
- **Reuse scan:**
  - `audit-ticket` already fetches the full issue thread, downloads and reads every body/comment image, treats newer comments as amendments, and records each requirement's short text plus body/comment-author-date/image source.
  - Its execution recipe weakens that provenance: an edited body preserves intent paragraphs but not an evidence index; a split successor carries open items and gaps but not every originating author, exact source link, or image reference.
  - `executing-tickets-with-subagents` requires the full thread and attached images before planning, but its durable ledger does not require a source-evidence map and its endgame does not require rereading a rewritten/successor ticket against the extraction.
  - Both workflows use `preflight-mutations` before issue writes, but neither explicitly posts investigation findings back to the durable source issue or re-fetches the final ticket to prove author/text/image/predecessor/successor preservation.
  - Ticket evidence is also relevant to filing and splitting workflows beyond stale-ticket audit, so an `audit-ticket`-only amendment may leave the same loss path elsewhere.
- **Architecture hypothesis:** Define one reusable ticket-evidence preservation contract and integrate it into existing ticket workflows, without creating another ticket-management interface. The contract should own provenance and closeout evidence; `audit-ticket` and ticket execution continue to own their actions.
- **Open design tree:**
  1. Should R09 create a shared preservation skill/contract used by ticket workflows, or deepen `audit-ticket` and `executing-tickets-with-subagents` independently? **Resolved:** add one shared preservation reference behind the existing ticket workflows; do not create another user-facing skill.
  2. Should the durable evidence record preserve full source text, short attributed excerpts plus source links, or only normalized requirements? **Resolved:** preserve every relevant item as an attributed exact excerpt with author, date, source URL, and image reference/checksum alongside its normalized requirement; omit unrelated discussion.
  3. Which issue is the durable home for investigation findings when a ticket is split or superseded? **Resolved:** the original issue remains the provenance hub and receives the complete investigation plus successor links; each successor carries only its relevant evidence and a predecessor backlink.
  4. After source fidelity and ownership are settled, how should screenshots be retained across predecessor/successor issues without losing access or context? **Resolved:** reuse accessible original attachment URLs with source/checksum provenance; when successor readers cannot access them, re-upload the original bytes and record both URLs/checksums; never replace images with descriptions.
  5. What predecessor/successor links and authoritative-status markers must each final ticket contain? **Resolved:** the original declares itself the authoritative provenance record in an `Investigation and successors` section; successors name `Split from #N`, scoped evidence IDs, and dependency-relevant sibling links.
  6. What exact reread/read-back comparison closes the workflow, and what happens when the final ticket drops evidence? **Resolved:** re-fetch and reread every final issue and rendered image, compare evidence IDs/excerpts/authors/links/checksums with the source map, and block closure or mark a successor incomplete until omissions are repaired.
- **Decisions:**
  1. **Architecture:** Deepen `audit-ticket` and `executing-tickets-with-subagents` with one shared ticket-evidence reference loaded only by evidence extraction, rewrite, or split branches. Do not add a standalone preservation skill or another ticket interface.
  2. **Evidence fidelity:** For every relevant source item, preserve an exact excerpt plus author, date, direct source URL, and image reference/checksum, paired with the normalized requirement it supports. Exclude unrelated discussion; summaries supplement rather than replace evidence.
  3. **Durable issue:** Keep the original issue as the provenance hub even when it closes. Post the complete investigation there and add every successor link. Each successor contains only evidence relevant to its scope and links back to the predecessor.
  4. **Screenshot retention:** Reuse an original GitHub attachment URL when the intended successor readers can access it and retain its source comment plus checksum. If access fails, re-upload the exact downloaded bytes and record original URL, new URL, and matching checksum. A prose description never replaces the image.
  5. **Linkage and authority:** Add an `Investigation and successors` section to the original issue and label it the authoritative provenance record. Each successor says `Split from #N`, lists its scoped evidence IDs, and links dependency-relevant sibling successors. The original links every successor.
  6. **Closeout:** After every issue mutation, re-fetch and reread the rendered original and all successors, including opening each referenced image. Compare evidence IDs, exact excerpts, authors, source/backlinks, successor links, and image checksums with the source map. Missing evidence blocks closure or leaves that successor explicitly incomplete until repaired and reread.
- **Proposed implementation shape:** Add one direct ticket-evidence reference under the existing ticket workflow most suitable as its shared home, then point `audit-ticket` and `executing-tickets-with-subagents` to it at intake and rewrite/split closeout. Keep action decisions and GitHub writes in their current skills, reuse `preflight-mutations`, update README descriptions only if behavior discovery changes, and add no new skill or evaluator.
- **Shared-understanding confirmation:** Confirmed by the user on 14 August 2026. Grill complete.
- **Final artifact:** `skills/audit-ticket/references/ticket-evidence.md`, with intake and closeout pointers from `audit-ticket` and `executing-tickets-with-subagents`.
- **Verification:**
  - The repository structural verifier passed across 25 skills and 59 Markdown files; its only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - Swift Foundation parsed the five affected Markdown files, and `git diff --check` passed.
  - The workflow contract was inspected for direct intake and closeout pointers, continued `preflight-mutations` ownership, original-issue authority, scoped successor evidence, image-byte/checksum preservation, and a blocking rendered reread.
  - The first acceptance review found two Serious gaps: bundled-ticket intake used rendered `--comments` output without structured comment provenance, and follow-up preflight did not bind the original investigation write plus every successor and relationship write into one exact batch.
  - The repair fetches structured issue JSON including the body and each comment's author, creation time, and direct URL. Its single preflight batch now includes current original guards, the complete investigation payload, every successor payload, every predecessor/successor/dependency link, and the full rendered read-back plan; writes outside that batch are excluded.
  - The focused affected-area recheck found zero Critical and zero Serious issues after both repairs.
  - Python compilation passed for the repository verifier, which now resolves explicit sibling-skill reference paths; the verifier passed across 25 skills and 59 Markdown files.
  - No live GitHub mutation or custom evaluator was run because the implementation changes agent instructions rather than an external issue. R09 is complete.

### R10 — Artifact lifecycle manager

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Artifacts are valuable but proliferated, competed, or lost unique evidence during consolidation.
- **Source specification:** Maintain one canonical URL; track sources and superseded artifacts; deduplicate without discarding unique findings; verify links and duplicate status at closeout.
- **Reuse scan:**
  - The global hosted-report rule requires findings, reports, audits, and lists to be reviewable HTML artifacts, but says nothing about authority, consolidation, or supersession after creation.
  - `done` verifies one rendered artifact and its links or published consumer; it does not determine which of several artifacts is canonical or whether consolidation preserved unique evidence.
  - `preflight-mutations` owns authorization, exact remote mutation targets, recovery, and authoritative read-back. It should gate lifecycle writes, not decide artifact semantics.
  - The R09 ticket-evidence contract is the closest provenance analog but must remain ticket-scoped. `converge-reviews` and `review-pr` already own stable finding IDs, dispositions, and rolling-review deduplication; R10 should cite those IDs instead of copying their state.
  - Batch review can produce a consolidated report, but no general workflow records its source set, elects one canonical URL, marks predecessors superseded, or re-fetches competing artifacts at closeout.
  - Setup-sync manifests, backup checksums, and ticket provenance solve domain-specific lifecycle problems; none should become a hidden general artifact registry.
- **Concrete gap:** No workflow inventories all source report artifacts before consolidation, accounts for each unique finding as carried/dismissed/retained by reference, elects and announces one canonical artifact, records reciprocal supersession links, and verifies rendered links plus remote duplicate status at closeout.
- **Boundaries:** Reuse `preflight-mutations` for writes and `done` for acceptance. Do not absorb ticket provenance, review finding-state ownership, task-status ledgers, build artifacts, QA screenshots, backups, generated code, or setup-sync files. Do not introduce a hidden registry or provider-specific evaluator without evidence.
- **Open design tree:**
  1. Should R10 be only a rule/reference wired into known producers, or a narrowly invoked coordinator for consolidating, replacing, or canonicalizing hosted review/research/report artifacts? **Resolved:** create a narrow coordinator skill; do not rely only on producer wiring or broaden `done` into lifecycle ownership.
  2. After architecture is settled, which artifact types and entry conditions are in scope? **Resolved:** govern durable hosted reviews, research, audits, findings, and reports only when consolidating, replacing, superseding, or choosing a canonical artifact. Exclude first-time creation, routine edits, temporary files, tickets, PR finding state, build outputs, screenshots, backups, and setup manifests.
  3. After scope is settled, where does the lifecycle record live and how is canonical authority represented? **Resolved:** keep lifecycle state in the canonical report itself, with a stable ID, canonical URL, source URLs, and superseded-artifact list. Add a short canonical-replacement marker to each writable predecessor. Keep draft state inline or in an existing authorized ledger; create no separate registry.
  4. After authority is settled, what exact per-finding/source accounting permits deduplication without evidence loss? **Resolved:** build a source-item map in which every source finding ID and URL has exactly one disposition—`carried`, `merged`, `dismissed`, or `retained by reference`—plus its canonical destination ID or dismissal rationale. Preserve links to source evidence instead of copying whole reports.
  5. After the record and accounting are settled, what mutation preview, supersession, link, and duplicate-status read-back closes the workflow? **Resolved:** preview one complete logical publication plan, partition it into mutation cards only where `preflight-mutations` requires separate authority or guard domains, and publish only ready dependency-satisfied cards. Then re-fetch the canonical report and every predecessor. Verify canonical and supersession markers, source and predecessor links, every source-item disposition, rendered links, and remote duplicate status. Record unwritable predecessors in the canonical report; block completion on any writable competing authority, broken required link, or unaccounted source item.
- **Decisions:**
  1. **Architecture:** Create a narrowly invoked lifecycle coordinator for consolidating, replacing, superseding, or choosing the canonical hosted review/research/report artifact. It coordinates existing owners: `preflight-mutations` gates writes, `done` verifies rendered and published acceptance surfaces, ticket evidence stays with R09, and review finding state stays with its source workflow.
  2. **Scope and activation:** Activate only from explicit lifecycle intent involving durable hosted reviews, research, audits, findings, or reports. Do not trigger for first-time report creation, routine edits, temporary artifacts, tickets, PR finding-state records, build outputs, screenshots, backups, or setup manifests.
  3. **Authority record:** The canonical report owns its lifecycle section: stable artifact ID, canonical URL, complete source URLs, and the artifacts it supersedes. Each writable predecessor gets a concise `Superseded by <canonical URL>` marker. Draft lifecycle state remains inline or in an already-authorized ledger; do not create a registry merely to store it.
  4. **Lossless consolidation:** Before publishing, map every source finding ID and URL to exactly one of `carried`, `merged`, `dismissed`, or `retained by reference`. A carried or merged item names its canonical destination ID; a dismissal records its rationale. Keep source evidence reachable by link rather than copying entire reports.
  5. **Mutation and closeout:** Build and preview one complete logical publication plan, partitioned into mutation cards only where `preflight-mutations` requires different authority or guard domains. Execute only ready cards in dependency order. Re-fetch the canonical report and all predecessors and verify authority markers, reciprocal links where writable, source-item accounting, rendered links, and duplicate status. An unwritable predecessor is acceptable only when the canonical report identifies it and records why it could not be marked; writable competing authority or missing evidence blocks completion.
- **Proposed implementation shape:** Add one narrowly model-invoked skill for explicit consolidation, replacement, supersession, and canonicalization requests involving hosted analytical artifacts. Keep its complete lifecycle protocol in one `SKILL.md`, register it in the README and routing catalog, add no hidden registry or bespoke evaluator, and hand mutation safety and final acceptance to `preflight-mutations` and `done`.
- **Shared-understanding confirmation:** Confirmed by the user on 14 August 2026. Grill complete.
- **Final artifact:** `skills/manage-report-lifecycle/`, with README discovery and lightweight routing cases.
- **Verification:**
  - The repository structural verifier passed across 26 skills and 60 Markdown files; its only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - Ruby's standard YAML parser accepted the skill frontmatter and generated `agents/openai.yaml`. The skill creator's optional validator could not start because PyYAML is unavailable; no dependency was installed.
  - Swift Foundation parsed the skill, README, and ledger Markdown; the trigger catalog parsed as JSON; `git diff --check` passed.
  - The first acceptance review found two gaps: inventory did not require one authoritative discovery query proving the competing report set was complete, and routing data did not exercise routine edits, ticket lifecycle, or PR finding-state exclusions.
  - The repair records and classifies every match from one broad host/workspace query and repeats that exact query at closeout. Three lightweight negative cases now cover the missing exclusion branches.
  - Mandatory parallel review found four Serious gaps: canonical election could target a nonexistent hosted object; one mutation card could cross ownership or confirmation domains; discovered competing authorities were not exhaustively bound as predecessors; and repeated discovery did not invalidate completion when its stable-ID set drifted.
  - The repair requires an existing hosted writable canonical candidate with a known URL and guard, models one complete publication plan partitioned into domain-correct mutation cards, gives every discovered match a final canonical/predecessor/unrelated classification, and returns discovery drift to inventory and preflight.
  - The review also found one Moderate identity gap. The lifecycle Artifact ID is now stable across replacements while each elected version records its separate host object ID and canonical URL.
  - A Moderate request for fixture-backed routing evidence is deferred: R10 explicitly adds routing catalog data without a live evaluator, and fixture expansion is outside this bounded implementation. The catalog remains schema-validated routing data rather than a claimed behavioral pass.
  - The affected-area rechecks after repair and simplification each reported zero Critical and zero Serious findings. The simplicity pass removed duplicated mutation mechanics and aligned the ledger with the publication-plan contract; no added code comments exist.
  - No hosted report mutation was run because the implementation changes the coordinator instructions rather than an external report. No bespoke evaluator was added. R10 is complete.

### R11 — Merge-readiness evidence card

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `complete`
- **Rationale:** Directly answers recurring “are we good?”, “what is left?”, and “no regression?” loops.
- **Source specification:** Map each request item to implementation; list tests, browser, database, CI, and review evidence; separate verified, assumed, deferred, and pending; state the exact next action.
- **Known overlap to resolve:** `done` correctness accounting and completion reporting.
- **Reuse scan:**
  - `done` already owns the final cross-surface verdict, six acceptance lanes, direct boundary evidence, `verified`/`assumed`/`deferred`/`blocked`/`not-applicable` states, an evidence ceiling, and the exact next action.
  - `file-pr` already requires a verified `done` report before opening a PR and must not invent a replacement verdict. Its PR body can still compress or omit evidence because it does not require a request-item map or named evidence facets.
  - `parallel-review` and `converge-reviews` own review findings, coverage, dispositions, and convergence; browser QA, database read-back, and CI are evidence suppliers rather than readiness owners.
  - `review-pr` reports PR review state but does not map the originating request to implementation or prove tests, browser, database, and CI together.
- **Concrete gaps:**
  - `done` maps requested outcomes to lanes but its final card has only one row per lane, so it does not prove every request item has an implementation and acceptance observation.
  - Tests and review are buried in the Code lane, database is implicit, and CI is unnamed; the user cannot scan those five evidence facets in one place.
  - `pending` is missing. Current states distinguish intentional postponement (`deferred`) and unavailable/failed verification (`blocked`), but not ordinary unfinished work or evidence that has not yet run.
  - `file-pr` can turn the richer completion evidence into a lossy new summary unless it consumes the request map and evidence index directly.
- **Architecture hypothesis:** Deepen `done` as the sole readiness-card producer and make `file-pr` consume that card. Do not add a second merge-readiness skill, ledger, or shared schema file unless the card proves too large to keep in the two always-used workflows.
- **Open design tree:**
  1. Should R11 deepen `done` and its `file-pr` handoff, deepen `done` alone, or create a separate readiness skill? **Resolved:** deepen `done` as the sole readiness-card producer and require `file-pr` to consume that card; add no separate skill or ledger.
  2. After ownership is settled, what exact request-item rows and evidence facets belong in the card? **Resolved:** add two compact tables to `done`: a request-coverage table with `Request item | Implementation/deliverable | Acceptance evidence | State | Gap/next action`, and an evidence index with fixed `Tests | Browser | Database | CI | Review` rows carrying exact observations or artifacts, state, and gap. Keep the existing six-lane table as the acceptance-boundary authority rather than duplicating it.
  3. After card shape is settled, how should `pending` differ from `deferred`, `blocked`, and `assumed`? **Resolved:** `pending` means required work or evidence is waiting on an unmet prerequisite or has not been attempted; `deferred` means intentionally postponed with a named owner and resume condition; `blocked` means a prerequisite-ready action was attempted and failed or cannot proceed; `assumed` means only indirect evidence exists; `verified` requires direct acceptance evidence; `not-applicable` is genuinely outside scope.
  4. After states are settled, what makes overall readiness verified and what exact next action is reported otherwise? **Resolved:** subject only to the bounded `ready-to-publish` exception in decision 7, readiness is `ready` only when every request item and required acceptance lane is `verified` and every evidence-index facet is `verified` or `not-applicable`. Any required `pending`, `assumed`, `deferred`, or `blocked` row otherwise makes it `not ready`. Report the first dependency-ready unresolved action as the exact next action.
  5. After readiness semantics are settled, how must `file-pr` reuse the card without restating or weakening its evidence? **Resolved:** require the request-coverage table, evidence index, lane table, verdict, and exact next action from the current `done` run. Derive `What changed` from verified request rows and `How to verify` from exact evidence-index observations. A missing, stale, or non-ready card returns to `done`; `file-pr` does not invent evidence or attach the full internal card verbatim.
  6. After the handoff is settled, what exact request and repository snapshot binds the card so `file-pr` can reject stale evidence? **Resolved:** record the originating request summary, base commit, current head, and working-tree/diff hash. `file-pr` recomputes them; any changed request scope, head, or diff makes the card stale and returns to `done`.
  7. Acceptance review exposed a circular gate: `done` cannot give a final ready verdict before PR publication and PR-only CI/review evidence exist, while `file-pr` cannot publish until it receives a ready card. What bounded pre-publication state may `file-pr` consume, and how does publication return to `done` for the final verdict? **Resolved:** `done` may issue `ready-to-publish` only when every pre-publication requirement is verified and the unresolved required rows depend solely on the PR existing. `file-pr` may consume that bounded state, publish and authoritatively re-fetch the remote branch and PR, then return to `done`; only the post-publication `done` run may issue final `ready` after CI, review, and every other applicable row resolve.
- **Decisions:**
  1. **Ownership:** `done` remains the single authority for readiness and produces the richer evidence card. `file-pr` consumes its request coverage and evidence index rather than reconstructing readiness. Review, browser, database, and CI workflows remain evidence suppliers. Add no merge-readiness skill, ledger, or shared schema file.
  2. **Card shape:** Add one request-coverage row per originating request item and one fixed evidence-index row for each of Tests, Browser, Database, CI, and Review. Each row names direct evidence, state, and its gap or next action. Preserve the six-lane table as the only acceptance-surface map.
  3. **States:** Use `pending` for required work or evidence waiting on an unmet prerequisite or not yet attempted. Reserve `deferred` for intentional postponement with an owner and resume condition, `blocked` for a prerequisite-ready action that failed or cannot proceed, `assumed` for indirect evidence, `verified` for direct acceptance evidence, and `not-applicable` for a surface outside scope.
  4. **Verdict:** Derive readiness from the tables. Subject only to decision 7's bounded `ready-to-publish` exception, every request item and required lane must be `verified` and every evidence facet must be `verified` or `not-applicable` for final `ready`. Any required `pending`, `assumed`, `deferred`, or `blocked` row otherwise yields `not ready`. Name the first dependency-ready unresolved action as the exact next action.
  5. **PR handoff:** `file-pr` requires the current `done` request table, evidence index, lane table, verdict, and exact next action. It derives `What changed` from verified request rows and `How to verify` from exact evidence observations. Missing, stale, or non-ready evidence returns to `done`; the PR workflow neither reconstructs evidence nor copies the full internal card into every PR.
  6. **Currency:** Bind the card to the originating request summary, base commit, current head, and working-tree/diff hash. `file-pr` recomputes those values and returns to `done` whenever request scope, head, or diff changed.
  7. **Publication transition:** The sole exception to decision 4's final-ready rule is `ready-to-publish`, a bounded handoff rather than a completion verdict. It is allowed only when all pre-publication rows are verified and every unresolved required row is explicitly PR-dependent. `file-pr` publishes, verifies the remote branch and PR from authoritative read-back, and returns the evidence to `done`; final `ready` still requires CI, review, publication, and all other applicable rows to satisfy the strict verdict.
- **Proposed implementation shape:** Amend `done` in place with the request-coverage table, fixed evidence index, expanded state vocabulary, strict row-derived verdict, exact next action, and snapshot binding. Amend `file-pr` only at its completion precondition and body derivation steps so it consumes the card. Update README descriptions only if discovery wording changes; add no new skill, schema file, ledger, trigger cases, or evaluator.
- **Shared-understanding confirmation:** Confirmed by the user on 14 August 2026. Grill complete.
- **Final artifact:** `skills/done/SKILL.md` as the sole readiness-card authority and `skills/file-pr/SKILL.md` as its currency-checking consumer, with their README descriptions updated.
- **Verification:**
  - Acceptance review found one Critical circular publication gate and five Serious execution gaps: non-Git currency was undefined; snapshot commands were not executable; PR base currency was incomplete; commit ordering was underspecified; and row-state vocabulary was inconsistent.
  - The confirmed repair adds a bounded `ready-to-publish` transition, external-target currency, safe alternate-index commands, refreshed PR-base and merge-base binding, exact append-only commit enumeration, and one state vocabulary. `file-pr` now returns authoritative remote-branch and PR evidence to a post-publication `done` run instead of claiming completion.
  - The affected-area recheck found two remaining Serious currency gaps: the card did not bind the exact branch through push and PR read-back, and a successful commit transition did not prove the committed tree still matched the verified snapshot with a clean worktree.
  - The repair records the exact branch and invalidates renames or switches, binds the push target and PR head to that branch, and requires the same clean-status and exact-tree content seal both before push and before final readiness.
  - Mandatory review then found seven remaining gaps: `pending` and `blocked` were not exclusive; `file-pr` did not inspect the alternate-index diff hunk-by-hunk immediately before commit; mixed external currency was incomplete; base-tip currency was missing; multi-part evidence facets could hide their weakest subcheck; the card templates omitted their verdict fields; and non-PR Git carried ambiguous PR fields.
  - The consolidation repair makes prerequisite readiness the pending/blocked boundary, adds reproducible candidate-diff accounting and last-moment currency validation, records mixed external targets and the remote base tip, aggregates evidence facets from preserved subchecks, completes both card templates, and marks PR currency not applicable for non-PR Git.
  - The final simplify review found four blocking clarity gaps: the final-ready rule did not name its sole publication exception; a requested non-PR commit depended circularly on final readiness; base selection had no authoritative owner; and `file-pr` duplicated scope accounting across two gates. It also required the README usage line to state the handoff prerequisite and a mutation preflight before GitHub writes.
  - The repair makes the exception explicit, validates non-PR commits before deriving final readiness, centralizes base election in `done`, keeps one candidate-diff accounting pass with snapshot invalidation, sharpens README discovery, and applies `preflight-mutations` immediately before push and PR creation.
  - The final affected-area check found two execution blockers: base discovery still read cached remote-tracking branches, and one combined push-plus-PR preflight became a multi-step batch without an authorized durable home.
  - The repair queries authoritative remote heads directly and uses two independent inline single-step mutation cards, verifying the landed branch before preflighting PR creation and preserving that partial-state evidence if the second card cannot proceed.
  - The exact alternate-index sequence ran from the repository root and left the real index byte hash unchanged. The repository structural verifier passed across 26 skills and 60 Markdown files; its only warning is the pre-existing ignored `license` key in `git-commit` frontmatter.
  - Swift Foundation parsed both changed skills, the README, and this ledger; `git diff --check` passed. Code, runtime, browser, database, CI, and network checks are not applicable to these agent-consumed Markdown changes. No new skill, schema, trigger, evaluator, commit, push, or PR was added.
  - The final affected-area recheck reported zero Critical and zero Serious findings after authoritative remote-base discovery and independent push/PR-create preflights were added. R11 is complete.

### R12 — Non-interactive tooling canary

- **Priority:** P1
- **Proposed destination:** Skill
- **Status:** `declined`
- **Rationale:** A package-manager firewall wrapper broke non-interactive pnpm use and forced development workflows to bypass the workspace runner.
- **Source specification:** Test interactive and non-interactive shells; exercise development, test, and workspace-build commands; verify dependent package outputs; document intentional bypasses and their cost.
- **Reuse scan:**
  - `done` requires repository-native build and test checks but does not compare shell modes, executable resolution, workspace-runner traversal, output freshness, or bypass cost.
  - `fix-ts-errors` owns only the TypeScript loop and assumes an available workspace command; it does not discover or test development, test, and build scripts.
  - `systematic-debugging` investigates environment differences after a failure but provides no proactive canary or reusable evidence card.
  - `executing-tickets-with-subagents` records known environment quirks and fallbacks without discovering them. `sync-agent-setups` verifies agent hooks, not package-manager wrappers or workspace tooling.
  - The trigger evaluator runs fresh non-interactive agent sessions but measures skill routing; reusing it would add an unrelated networked evaluator.
- **Concrete gap:** No workflow discovers the repository-native package manager and runner, executes representative development/test/workspace-build commands in both interactive and actual non-interactive contexts, verifies dependent outputs, and records the guarantees lost by intentional bypasses.
- **Boundaries:** `done` should consume a current canary result only when tooling or shell behavior changed. Keep TypeScript remediation in `fix-ts-errors`, root-cause diagnosis in `systematic-debugging`, browser flows in `browser-qa`, and runner-specific repository facts in project rules. Do not print full environments or run interactive and non-interactive development servers concurrently.
- **Architecture hypothesis:** Add one compact `tooling-canary` skill and one conditional `done` handoff. Keep the complete procedure in one `SKILL.md`; add no helper script, reference tree, fixture, or bespoke evaluator initially.
- **Decision:** Declined. The evidence is one narrow historical wrapper failure, while existing diagnostic workflows can investigate a concrete recurrence. A permanent proactive skill and conditional `done` integration would add disproportionate invocation and maintenance cost. Reconsider only if interactive/non-interactive parity failures recur across projects.
- **Final artifact:** This decision record; no skill or global rule added.
- **Verification:** Confirmed that no R12 implementation files were created. The overlap scan and decline rationale remain preserved here.

### R13 — Material-state progress updates

- **Priority:** P1
- **Proposed destination:** Global rules
- **Status:** `complete`
- **Rationale:** Universal, short, and cheap to enforce on every long-running task.
- **Source specification:** Report completed, active, blocked, and next; update only on a material state, ETA, decision, or blocker change.
- **Reuse scan:**
  - The live Claude Code source of truth says to track multi-step work and give a high-level summary at each step, but it does not define a compact status shape or material-only cadence.
  - `executing-tickets-with-subagents` already owns detailed durable ledgers and a material-only update cadence for bundled and unattended runs. Its handoff reports completed, active, blocked, pending decisions, and next action.
  - `done` owns final readiness rather than ongoing progress and should not absorb this rule.
- **Concrete gap:** Ordinary long-running work outside bundled or unattended execution still encourages per-step narration and has no standard `Completed / Active / Blocked / Next` projection.
- **Authority boundary:** `~/.claude/CLAUDE.md` is the live source of truth. `~/.codex/AGENTS.md` is already a symlink to it. `reference/CLAUDE.md` is a repository reference copy with unrelated pre-existing divergence, so R13 should make the same surgical Task Management edit there without wholesale synchronization. Other agent targets remain outside scope because `sync-agent-setups` is user-invoked only.
- **Architecture hypothesis:** Replace the existing per-step narration clause with one short global material-state rule. Require a durable ledger only when compaction, handoff, or multiple agents are plausible; do not add a skill, template, or evaluator.
- **Decision:** For long-running work, report `Completed`, `Active`, `Blocked`, and `Next`. Send an update only when one of those fields changes materially, a decision changes, or the ETA changes. Keep the same four fields in one durable ledger only when compaction, handoff, or multiple agents are plausible.
- **Implementation shape:** Replace the existing global per-step narration clause with the compact rule in `~/.claude/CLAUDE.md`; verify the Codex symlink exposes it; apply only the matching surgical edit to `reference/CLAUDE.md`. Add no skill, template, evaluator, or unrelated synchronization.
- **Open design tree:** Empty; the user confirmed the complete design.
- **Final artifact:** `~/.claude/CLAUDE.md` is authoritative; `~/.codex/AGENTS.md` consumes it through the existing symlink; `reference/CLAUDE.md` carries the same surgical reference-copy edit.
- **Verification:** Exact wording appears once in the live Claude source, Codex symlink surface, and repository reference; the superseded per-step narration clause appears nowhere on those surfaces. The repository verifier passed across 26 skills and 60 Markdown files with only the pre-existing ignored `license` warning in `git-commit`. Swift Foundation read all four affected Markdown surfaces, `git diff --check` passed, and the added-comment scan was clean. The focused review and one affected-area recheck ended with zero Critical and zero Serious findings; the proportional simplify pass found no actionable simplification. TypeScript, runtime, browser, database, and CI checks are not applicable to these instruction-only Markdown changes.

### R14 — Evidence reuse and ownership

- **Priority:** P1
- **Proposed destination:** Global rules
- **Status:** `complete`
- **Rationale:** Universal guardrail against redundant subagents and reviewer churn.
- **Source specification:** Never assign the same scope to two agents; treat completed reviewer output as valid until the diff changes.
- **Reuse scan:**
  - The global orchestration rules require subagents but do not check active owners or completed evidence before dispatch.
  - The unattended scheduler already permits one active mutation owner per task and separate read-only reviewers. `executing-tickets-with-subagents` and `review-pr` use distinct lenses; `parallel-review` is an explicit independent-review contract over one target.
  - `converge-reviews` already owns detailed evidence currency: request, baseline, covered paths and content hash, roster/lens, partial invalidation, and bounded review rounds.
  - `verify-claims` intentionally requires a fresh independent recheck when a decision-driving conclusion materially reverses.
- **Source correction:** Literal “same scope” would prohibit valuable independent review unless scope includes the target, task, and lens. Literal “until the diff changes” would discard unaffected evidence after unrelated changes and retain stale evidence after a request, baseline, or lens change.
- **Architecture hypothesis:** Add one compact global dispatch rule: check owners and completed evidence first; assign one active execution owner per target/task; permit read-only reviewers to share a target under distinct lenses or an explicit independent-review or recheck contract; reuse evidence while its request, baseline, covered content, and lens match, invalidating only affected coverage. Leave hashes, state, and round mechanics in `converge-reviews`.
- **Decision:** Before dispatch, check active owners and completed evidence. Give each target/task one active execution owner. Parallel read-only reviewers may share a target only under distinct named lenses or an explicit independent-review or recheck contract. Reuse reviewer evidence while its request, baseline, covered paths and content, and lens still match; invalidate and rerun only affected coverage when one changes.
- **Implementation shape:** Add one short global rule under orchestration in `~/.claude/CLAUDE.md`; verify the Codex symlink surface; apply the same surgical addition to `reference/CLAUDE.md`. Keep detailed hash, state, and round semantics solely in `converge-reviews`; add no skill, template, or evaluator.
- **Open design tree:** Empty; the user confirmed the complete design.
- **Final artifact:** `~/.claude/CLAUDE.md` is authoritative; `~/.codex/AGENTS.md` consumes it through the existing symlink; `reference/CLAUDE.md` carries the same surgical reference-copy addition.
- **Verification:** Exact wording appears once in the live Claude source, Codex symlink surface, and repository reference. The repository verifier passed across 26 skills and 60 Markdown files with only the pre-existing ignored `license` warning in `git-commit`. Swift Foundation read all four affected Markdown surfaces, `git diff --check` passed, and the added-comment scan was clean. The focused review found two ownership-boundary issues; after repair, one affected-area recheck ended with zero Critical and zero Serious findings. The proportional simplify pass found no actionable simplification. TypeScript, runtime, browser, database, and CI checks are not applicable to these instruction-only Markdown changes.

### R15 — GSM3 operating facts

- **Priority:** P0
- **Proposed destination:** Project rules
- **Status:** `researching`
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
- Completed the R05 overlap scan. `done` is the mandatory entry point but assumes code; existing browser, claim, mutation, and board skills cover some acceptance boundaries while configuration, documentation, metadata, and publication lack routing. Advanced R05 to `grilling`.
- Recorded R05 decision 1: deepen `done` into the surface-aware completion router rather than create a second completion command or hide the core routing contract in a separate reference.
- Recorded R05 decision 2: the agent infers and displays acceptance lanes from request, artifacts, and actions, while the user retains an override.
- Recorded R05 decision 3: use six practical lanes with minimum proof at the actual code, browser, rendered-doc, invocation, authoritative-data, or published-consumer surface.
- Recorded R05 decision 4: assign per-lane `verified`, `assumed`, `deferred`, `blocked`, or `not-applicable` states and cap the overall verdict below verified whenever a required lane lacks verification. The grill frontier is empty pending confirmation.
- User confirmed the complete R05 design. Reworked `done` as the single surface-aware completion router with six acceptance lanes, conditional code verification, delegated boundary checks, and a universal evidence ceiling. Moved R05 to `verifying`.
- Moved R05 to `verifying` after implementation; closure awaits the actual documentation and skill-invocation acceptance checks.
- Closed R05 after the changed Markdown parsed successfully and a fresh-agent acceptance review verified the skill's routing contract with zero Critical or Serious findings. Advanced R06 to `researching`.
- Completed the R06 overlap scan. The bundled-ticket orchestrator already owns waves and a durable ledger, while the global unattended rule supplies only the trigger, authority boundary, and morning-summary requirement. Advanced R06 to `grilling` with architecture, activation, and pool ownership as the first frontier.
- Recorded R06 decisions 1–3: deepen the existing orchestrator, activate on explicit away/keep-going delegation without a task-count threshold, and use a kickoff-fixed pool of at most three workers with one mutation owner per task and independent read-only review.
- Recorded R06 decisions 4–5: retry capacity once after a worker-slot transition, then block only that task; persist every task transition in the existing ledger while surfacing only material updates and maintaining a fixed morning-handoff section. The grill frontier is empty pending confirmation.
- User confirmed the complete R06 design. Implemented the unattended branch and its single disclosed scheduler reference, aligned the global authority pointer, and moved R06 to `verifying` for one bounded acceptance review.
- Repaired the bounded R06 acceptance findings by making reference loading portable, preventing fixed-zero-pool deadlock, assigning owners only after successful dispatch, and spelling out the unattended commit/push/PR verification gate. R06 remains `verifying` pending one affected-area recheck.
- Repaired the remaining affected-area finding by binding zero-slot initialization retries and blocking to the selected task rather than the entire runnable queue. R06 remains `verifying` pending the final affected-area recheck.
- Closed R06 after the final exact-line recheck confirmed task-bound zero-slot retries and reported zero Critical and zero Serious findings. Advanced R07 to `researching`.
- Completed the R07 inventory. Shared skill symlinks already exist but the Claude and Codex sets have drifted, two Claude custom slash workflows lack Codex equivalents, backups are fragmented, and no workflow verifies parity at the invocation surface. Advanced R07 to `grilling` with architecture, per-artifact authority, and sync scope as the first frontier.
- User corrected R07's authority model: Claude Code is the source of truth for all other agents. Replaced bidirectional/per-artifact authority with one-way Claude-outward propagation; downstream differences are drift, not upstream candidates.
- User corrected R07's invocation model: the setup-sync skill is user-invoked only. Automatic/model invocation is disabled, and no other workflow may start a sync implicitly.
- Recorded R07 scope: propagate Claude-authored behavioral setup only; exclude secrets, histories, caches, telemetry, and platform-managed content.
- Recorded R07 backup and portability decisions: preview and checksum-backup before writes, item-scoped collision blocking, and behavior-preserving exact-copy/adaptation/unsupported classification for custom workflows.
- Recorded R07 acceptance gates: full parse/discovery, per-entry picker checks where available, manual invocation of every custom workflow/adaptation, and representative manual invocation for bulk exact-copy skills. Unavailable surfaces cap the parity claim.
- Recorded R07 target and orphan decisions: preview all detected agents but mutate only confirmed targets; preserve downstream-only artifacts as orphaned drift unless deletion or promotion into Claude is separately authorized.
- Recorded R07 exact-copy storage: preserve shared symlinks to Claude's resolved sources, record resolved paths and checksums, and accept that authority is procedural rather than filesystem-isolated. The grill frontier is empty pending confirmation.
- User confirmed the complete R07 design. Implemented the manual-only `sync-agent-setups` workflow, registered its picker metadata and README entry, and moved R07 to `verifying` without performing an agent-setup sync or adding a bespoke evaluator.
- Repaired two Serious R07 acceptance findings by separating preserved or blocked rows from the independently ready preflight batch and binding each adaptation write to staged, checksummed bytes confirmed in the preview. R07 remains `verifying` pending one affected-area recheck.
- Closed R07 after structural, metadata, Markdown, explicit manual-invocation, and bounded contract-review checks. No setup state changed. Advanced R08 to `researching`.
- Completed the R08 overlap scan. Existing grilling tools ask good questions and `harden-plan` records richer run-local dispositions, but no workflow owns durable effective decisions, history, recap, undo, or dependency invalidation. Advanced R08 to `grilling`.
- Declined R08 as disproportionate after the user challenged its restrictiveness. Preserved the existing lightweight summaries, rationale capture, and irreversible-action confirmation instead of adding a cross-workflow decision state machine. Advanced R09 to `researching`.
- Completed the R09 overlap scan. Existing ticket intake reads full threads and images, but audit rewrites and successor tickets do not preserve a durable provenance map, require final-ticket reread, or guarantee investigation write-back. Advanced R09 to `grilling`.
- Recorded R09 decisions 1–3: amend the existing ticket workflows through one shared reference, preserve attributed exact excerpts and image provenance, and keep the original issue as the durable investigation hub with linked successors.
- Recorded R09 decisions 4–6: preserve screenshot bytes and access provenance, make predecessor/successor authority explicit, and require a live final reread against the evidence map before closure. The grill frontier is empty pending confirmation.
- Confirmed and implemented the R09 design as one shared evidence-preservation reference used by the existing ticket workflows. Advanced R09 to `verifying`; no GitHub issue was mutated.
- Repaired two Serious R09 acceptance findings by fetching structured comment provenance and binding the original investigation plus every successor and relationship write into one preflight batch. R09 remains `verifying` pending the affected-area recheck.
- Closed R09 after the focused affected-area recheck reported zero Critical and zero Serious findings and all applicable structural, Python, Markdown, and diff checks passed. Advanced R10 to `researching`.
- Completed the R10 overlap scan. Existing workflows own rendering, safe mutations, ticket provenance, and review finding state, but none owns general report-artifact authority, lossless consolidation, reciprocal supersession, or duplicate closeout. Advanced R10 to `grilling` with a narrow lifecycle-architecture frontier.
- Recorded R10 architecture: add a narrow lifecycle coordinator rather than a producer-only reference or more global completion prose. Scope and entry conditions are the next frontier.
- Recorded R10 scope: cover only explicit consolidation, replacement, supersession, or canonicalization of durable hosted analytical artifacts; exclude routine creation and unrelated artifact classes.
- Recorded R10 authority: lifecycle state lives in the canonical report, writable predecessors point to it, and no separate registry is introduced.
- Recorded R10 consolidation accounting: every source finding receives one explicit disposition and destination or rationale, while original evidence remains linked rather than duplicated.
- Recorded R10 closeout: preflight one exact publication batch, then re-fetch the canonical artifact and every predecessor to verify authority, links, item accounting, and duplicate status. The grill frontier is empty pending confirmation.
- User confirmed the complete R10 design. Implemented the focused `manage-report-lifecycle` coordinator with one compact protocol, UI metadata, README discovery, and lightweight routing cases. Advanced R10 to `verifying`; R11 remains pending.
- Repaired the two R10 acceptance gaps by making source-set discovery authoritative and repeatable and adding the three missing exclusion cases. R10 remains `verifying`; R11 remains pending.
- Repaired the mandatory R10 review findings by grounding canonical election in an existing hosted object, partitioning the complete publication plan by mutation domain, exhaustively binding competing authorities, invalidating closeout on discovery drift, and separating lifecycle identity from host-version identity. Deferred fixture-backed routing evidence as outside R10's no-evaluator scope. R10 remains `verifying`; R11 remains pending.
- Closed R10 after the mandatory review and post-simplification delta checks both reported zero Critical and zero Serious findings and all applicable structural, YAML, Markdown, JSON, and diff checks passed. Advanced R11 to `researching`.
- Completed the R11 overlap scan. `done` already owns readiness and `file-pr` already consumes its verdict; the missing behavior is request-item accounting, a named evidence index, a pending state, and lossless PR handoff. Advanced R11 to `grilling`.
- Recorded R11 ownership: deepen `done` as the sole readiness-card producer and require `file-pr` to consume it; do not add a competing readiness skill or ledger.
- Recorded R11 card shape: add a request-coverage table and a five-row evidence index while retaining the existing six-lane card as the acceptance-boundary authority.
- Recorded R11 states: distinguish ordinary pending work from intentional deferral, blockers, indirect assumptions, direct verification, and genuinely inapplicable evidence.
- Recorded R11 verdict: compute readiness strictly from request, lane, and evidence rows and surface the first dependency-ready unresolved action when not ready.
- Recorded R11 PR handoff: `file-pr` derives its change and verification sections from the current `done` card and returns missing, stale, or non-ready evidence to `done`.
- Recorded R11 currency: bind the readiness card to the originating request summary, base commit, current head, and working-tree/diff hash so changed scope or content invalidates it. The grill frontier is empty pending confirmation.
- User confirmed the complete R11 design. Implemented request coverage, five named evidence facets, `pending`, row-derived readiness, deterministic content currency, the expected append-only completion-commit transition, and a `file-pr` recomputation gate. Advanced R11 to `verifying`; R12 remains pending.
- Returned R11 to `grilling` after acceptance review found a circular gate between final readiness and PR publication. The pre-publication transition is open; five mechanical execution findings await the same repair pass.
- Recorded the R11 publication transition: a bounded `ready-to-publish` card may authorize `file-pr`, which must re-fetch the remote branch and PR and return to `done` for the final readiness verdict. The corrected frontier is empty pending confirmation.
- User confirmed the corrected R11 design. Repaired the circular publication gate and five execution findings with two-phase readiness, conditional external currency, executable snapshot and commit checks, refreshed PR-base binding, and authoritative publication read-back. Advanced R11 to `verifying`; R12 remains pending.
- Repaired the two remaining R11 recheck findings by binding exact branch identity through push and PR read-back and sealing the committed content against the verified snapshot before publication and final readiness. R11 remains `verifying`; R12 remains pending.
- Consolidated the mandatory R11 review findings into the existing card and handoff: exclusive states, exact candidate-diff accounting, mixed external and base-tip currency, weakest-subcheck evidence aggregation, complete verdict headers, and an explicit non-PR Git lane. R11 remains `verifying`; R12 remains pending.
- Applied the final R11 simplify repairs: one explicit readiness exception, a non-circular non-PR commit transition, authoritative base resolution in `done`, one candidate-diff accounting gate, sharper README invocation guidance, and mutation preflight before GitHub writes. R11 remains `verifying`; R12 remains pending.
- Repaired the final two R11 execution findings by reading integration candidates directly from remote heads and splitting publication into independently gated push and PR-create mutations with authoritative read-back between them. R11 remains `verifying`; R12 remains pending.
- Closed R11 after the final affected-area recheck reported zero Critical and zero Serious findings and all applicable structural, alternate-index, Markdown, and diff checks passed. Advanced R12 to `researching`.
- Completed the R12 overlap scan. Existing workflows run checks or diagnose failures but none owns proactive interactive/non-interactive parity, workspace-runner traversal, dependent-output evidence, and bypass-cost accounting. Advanced R12 to `grilling`.
- User declined R12 after reviewing its purpose and proportionality. Recorded that one narrow historical wrapper failure does not justify a permanent proactive skill; existing diagnostic workflows remain the fallback if the problem recurs. Advanced R13 to `researching`.
- Completed the R13 overlap scan. Detailed material-state reporting already exists for unattended execution, while the global rule still encourages per-step narration. Advanced R13 to `grilling` with one proportionality decision: when the four-field status also needs durable persistence.
- Recorded the recommended R13 contract: four-field material-state updates with a durable ledger only when continuity risk warrants it. The grill frontier is empty pending confirmation.
- User confirmed the complete R13 design. Advanced R13 to `implementing` with `writing-for-agents` governing the two surgical global-rule edits.
- Implemented the confirmed R13 rule in the Claude Code source of truth and repository reference copy. Verified that the existing Codex symlink exposes the exact rule and advanced R13 to `verifying`.
- The focused R13 review found a stale aggregate status and ambiguous material-change grammar. Corrected the count to `1 verifying` and made materiality apply only to the four progress fields; decision and ETA changes remain explicit update triggers.
- Closed R13 after exact live/source/symlink checks, structural Markdown verification, focused review, one clean affected-area recheck, and a proportional simplify pass. Advanced R14 to `researching`.
- Completed the R14 overlap scan. Existing review workflows already reuse hash-bound coverage, while the global orchestration rule lacks a dispatch-time owner/evidence check. Advanced R14 to `grilling` with the independent-review exception as the only open decision.
- Recorded the recommended R14 contract: one active owner per target/task/lens, explicit distinct-lens or independent-recheck exceptions, and partial evidence invalidation. The grill frontier is empty pending confirmation.
- User confirmed the complete R14 design. Advanced R14 to `implementing` with `writing-for-agents` governing the two surgical global-rule additions.
- Implemented the confirmed R14 rule in the Claude Code source of truth and repository reference copy. Verified that the existing Codex symlink exposes the exact rule and advanced R14 to `verifying`.
- The focused R14 review found that target/task/lens ownership could permit two executors and that the exception did not clearly cover the existing explicit parallel-review contract. Tightened ownership to one execution owner per target/task and reserved lenses or explicit independent-review/recheck contracts for read-only reviewers.
- Closed R14 after exact live/source/symlink checks, structural Markdown verification, focused review, one clean affected-area recheck, and a proportional simplify pass. Advanced R15 to `researching`.
