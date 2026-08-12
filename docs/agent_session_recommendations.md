# Agent Session Recommendation Ledger

This is the authoritative source and recovery map for turning the 12 August 2026 Agent Session Retrospective into durable agent behavior. Resume by reading this file and executing `NEXT ACTION`; conversation memory and summaries are not run state.

## Run state

- **Objective:** Process every recommendation in source order. For each item, finish a `grill-me` design tree, obtain explicit confirmation of shared understanding, write the agreed artifact with `writing-for-agents`, verify it at its acceptance surface, and update this ledger before advancing.
- **Current item:** `R02 — External-state mutation preflight`
- **NEXT ACTION:** Inventory R02's overlap with existing mutation workflows, record the open design frontier, and begin its `grill-me` questions.
- **Progress:** 1 of 18 recommendations complete; 1 researching; 16 pending.
- **Canonical artifact:** `docs/agent_session_recommendations.md`
- **Source artifact:** Agent Session Retrospective, local research artifact dated 12 August 2026, served at `http://127.0.0.1:4173/` when captured.
- **Last updated:** 12 August 2026

### Working contract

1. Preserve source evidence in this ledger; later summaries supplement it.
2. Process one recommendation at a time in the order below unless the user explicitly changes the order.
3. Research environmental facts before asking the user. Ask the complete current decision frontier through `grill-me`; dependent decisions wait for a later round.
4. Treat the retrospective's destination as a proposal. The grill may conclude that the right result is a new skill, an amendment, shared reference, global rule, project rule, decision record, consolidation, or decline.
5. Begin implementation only after the grill frontier is empty and the user confirms shared understanding.
6. Write agent-consumed artifacts with `writing-for-agents`; for skills, also apply its skill mechanics and validate the final invocation surface.
7. Change an item's status only when its exit criterion is met. Record decisions, artifact paths, and verification evidence in that item's detail section.
8. Update `NEXT ACTION`, counts, the status table, item detail, and change log together after every material transition.

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
| R02 | P0 | External-state mutation preflight | Skill | `researching` | TBD | Resolve overlap and open grill |
| R03 | P0 | Calibrated project-board mutation | Skill | `pending` | TBD | Start after R02 closes |
| R04 | P0 | Review-ledger convergence | Skill | `pending` | TBD | Start after R03 closes |
| R05 | P0 | Surface-aware done | Skill | `pending` | TBD | Start after R04 closes |
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
- **Status:** `researching`
- **Rationale:** Low-frequency Git, board, and issue mistakes had outsized cost because they changed shared state.
- **Source specification:** Resolve target and ownership; inspect base, head, and dependencies; check published-history status; preview ambiguous splits or grouping; record reversibility and approval.
- **Decisions / final artifact / verification:** Pending.

### R03 — Calibrated project-board mutation

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Prevents the archive's most expensive correction and is reusable across project boards.
- **Source specification:** Resolve ownership before writes; ask for estimate unit and 3–5 anchors; preview a representative sample; handle umbrella tickets explicitly; re-fetch and total from the final write ledger.
- **Decisions / final artifact / verification:** Pending.

### R04 — Review-ledger convergence

- **Priority:** P0
- **Proposed destination:** Skill
- **Status:** `pending`
- **Rationale:** Retains the proven value of independent review without endless review waves.
- **Source specification:** Hash the reviewed diff; store reviewer coverage and disposition; rerun delta plus open findings only; cap convergence at three rounds; convert important remainder to issues.
- **Known overlap to resolve:** `review-pr`, `parallel-review`, and their persisted finding state.
- **Decisions / final artifact / verification:** Pending.

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
