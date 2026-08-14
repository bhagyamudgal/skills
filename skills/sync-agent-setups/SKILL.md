---
name: sync-agent-setups
description: Preview and sync Claude Code's user-authored behavioral setup outward to selected agents.
disable-model-invocation: true
---

# Sync Agent Setups

Claude Code is the only source of truth. This workflow inventories every detected non-Claude agent, but it writes only to targets the user confirms during this invocation. It never starts automatically.

## 1. Inventory source and targets

Discover Claude's active user-level setup from the current machine rather than assuming fixed paths. Inventory only user-authored behavior:

- global rules;
- skills;
- custom slash workflows;
- hooks; and
- non-secret behavioral settings.

Exclude credentials, conversation history, caches, telemetry, generated runtime state, and platform-managed content. Detect every installed non-Claude agent and its supported setup surfaces read-only. Record unavailable or ambiguous surfaces instead of guessing.

Resolve each Claude-visible source through any symlink and calculate its checksum. Read the target's current path, file kind, link target, and checksum without following a downstream difference back into Claude.

**Gate:** every source and detected target has a stable path, ownership classification, and explicit in-scope or excluded reason.

## 2. Produce the dry-run manifest

Classify every in-scope source-target pair and every downstream-only user-authored artifact:

| Classification | Meaning | Planned action |
|---|---|---|
| `exact-copy` | Target accepts the same format and semantics | Symlink the target to Claude's resolved source |
| `adaptation` | Behavior survives, but packaging, variables, tools, or invocation syntax differ | Generate a target-native artifact; preserve Claude unchanged |
| `unsupported` | A required capability cannot be reproduced | Leave untouched and record the missing capability |
| `orphaned-downstream-drift` | User-authored target content has no Claude source | Leave untouched pending a separate deletion or promotion decision |

Treat custom slash-workflow behavior as portable by default. Use `unsupported` only after verifying that the target cannot reproduce a required capability. An ambiguous collision is `blocked`; it does not block independent items.

Before previewing an `adaptation`, render its complete target-native bytes into a safe local staging path outside every source and target setup root. Record the staged path, content checksum, target format, and exact semantic delta from the unchanged Claude source. A failed or ambiguous rendering is `blocked`, not a future write-time decision.

Render a manifest before any write:

```markdown
### Setup sync manifest

- **Claude source roots:** <active Claude-visible roots>
- **Detected targets:** <agent and setup roots>
- **Excluded surfaces:** <surface and reason>
- **Proposed backup:** <timestamped path>

| ID | Target | Kind | Claude-visible source | Resolved source | Source checksum | Target path | Existing kind / checksum | Classification | Link target or staged path / checksum | Semantic delta | Planned action | Status / reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

For an exact copy, record both the proposed link target and resolved physical source. Assign one pre-confirmation status to every item:

- `ready` — the exact link target is resolved, or the adaptation's final bytes are staged and checksummed;
- `blocked` — a collision, incomplete classification, or unstaged adaptation prevents a safe write;
- `preserved-unsupported` — the target cannot reproduce required behavior; or
- `preserved-orphaned` — downstream-only user content remains untouched.

Summarize per target: item counts by classification, paths to change, unsupported behavior, orphaned drift, collisions, and acceptance surfaces. State that an exact-copy symlink shares physical content: editing through the downstream path also changes Claude's source, so authority is procedural rather than filesystem-isolated.

**Gate:** the manifest accounts for the full in-scope Claude inventory and all detected downstream user-authored artifacts, every adaptation's final bytes and semantic delta are previewable, and every item has exactly one status without proposing any import or deletion.

## 3. Confirm the write set

Ask the user to select or confirm the target agents from the preview. Detection is not write authorization. A confirmation covers only the named targets, `ready` item IDs, backup path, exact-copy link targets, staged adaptation paths and checksums, semantic deltas, and proposed actions shown in the current manifest.

Re-inventory after confirmation and rehash every staged adaptation. Any changed source checksum, target state, classification, path, selected target, staged bytes, or staged checksum invalidates that item and returns it to preview. Change confirmed `ready` items to `pending`; retain every `blocked`, `preserved-unsupported`, and `preserved-orphaned` row in the ledger.

**Gate:** every `pending` item belongs to an explicitly confirmed target and still matches its preview, while every non-ready item remains outside the mutation batch with its status and reason intact.

## 4. Preflight and back up

Immediately before the first backup or target write, invoke `preflight-mutations` for only the selected `pending` items. Include their target agents, source and target paths, current checksums and link targets, staged adaptation paths and checksums, semantic deltas, confirmation source, shared-symlink risk, timestamped backup path, invalidators, per-item recovery, and post-write read-back. Reference the complete ledger for context, but do not put `blocked`, `preserved-unsupported`, or `preserved-orphaned` items into the mutation card's targets or batch items. Continue only when this independently ready mutation batch returns `ready` with unchanged guards.

Create the confirmed timestamped backup before changing a target. Preserve for every affected path:

- its original path and whether it was absent, a file, directory, or symlink;
- symlink text without dereferencing it;
- resolved path and checksum when one exists; and
- enough content and permissions to restore the prior target state.

Write a backup manifest mapping each item ID to its recovery action. Verify the backup inventory and checksums before the first target mutation.

**Gate:** every pending target path has a verified recovery record, including preserved link metadata and resolved content evidence.

## 5. Apply confirmed items

Protect each target's check/write/read-back interval with the platform's native conditional or atomic write when it exposes one. Otherwise acquire a compact exclusive lock for that target in its parent directory with an atomic lock operation, record the lock path and item ID, and release it through a guaranteed cleanup path. The fallback lock serializes this workflow's writers; it is not a claim that unrelated processes honor universal compare-and-swap.

Under that protection, re-read and compare the target's file kind, symlink text and resolved path, checksum, and every applicable platform revision with the confirmed manifest. For an exact copy, also resolve and rehash the confirmed Claude source; for an adaptation, rehash the staged artifact. A mismatch preserves the target, marks the item `blocked`, and releases the lock without a write.

- `exact-copy`: replace only the confirmed target path with the recorded symlink to the just-revalidated Claude source.
- `adaptation`: write the confirmed staged bytes without regeneration, using a same-directory temporary file plus atomic replacement when the target surface supports it, and retain its source/target provenance in the manifest.
- `unsupported` and `orphaned-downstream-drift`: preserve current target state.
- `blocked`: preserve current target state and continue independent `pending` items.

Keep the protection until authoritative read-back matches the exact confirmed resulting kind, link target or bytes, and checksum. For an exact copy, resolve the installed link and require its checksum to equal the revalidated Claude source checksum before releasing the protection. A pre-write source, staged-byte, target-guard, or checksum mismatch preserves the target and returns the item to preview for re-confirmation. Any post-write mismatch, for either an exact copy or an adaptation, restores the verified backup under the same protection and verifies the original kind, symlink text, resolved path, content checksum, and permissions before release. A verified restoration marks the item `blocked`; a failed or inconclusive restoration marks it `failed`, preserves the protection where safe, and reports the exact backup recovery action. Record each attempted item from authoritative read-back. Never restart a partial run from an assumed clean state. Future changes to an exact-copy artifact originate at its Claude-visible source; editing through the downstream symlink changes that same shared file and violates the authority contract.

Deletion of orphaned drift and promotion of downstream content into Claude are separate decisions. Preview and preflight either operation as a new mutation batch.

**Gate:** every attempted item has a read-back state, and untouched classifications remain byte- and link-identical to their preflight state.

## 6. Verify each target

Verify targets independently:

1. Parse every written artifact.
2. Compare the target's complete discovered user-authored name set with the final manifest, accounting explicitly for supported exclusions and untouched platform-managed entries.
3. Check picker visibility for every changed user-invoked entry when the platform exposes a picker.
4. Manually invoke every changed custom workflow and every adaptation.
5. For bulk exact-copy skills, manually invoke a representative sample while parsing and discovering the full set.
6. Exercise each changed hook, setting, or global rule through the target's real consumer where that surface is available.

An unavailable picker, invocation surface, or consumer is an evidence ceiling for that target. Label it unavailable and withhold a full-parity claim. If evidence materially reverses the parity conclusion, invoke `verify-claims` before relying on the replacement conclusion.

Run `done` for the final evidence card. Include the backup manifest, final item ledger, per-target parse/discovery/picker/invocation/consumer evidence, unavailable surfaces, restore path, and exact next action.

**Done:** every detected target and source artifact is accounted for, only confirmed targets changed, every changed path is recoverable, and each target's parity claim is capped at its weakest acceptance surface.
