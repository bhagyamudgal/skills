# Dry-run manifest

Classify every in-scope source-target pair and every downstream-only user-authored artifact:

| Classification | Meaning | Planned action |
|---|---|---|
| `exact-copy` | Target accepts the same format and semantics | Symlink the target to Claude's resolved source |
| `adaptation` | Behavior survives, but packaging, variables, tools, or invocation syntax differ | Generate a target-native artifact; preserve Claude unchanged |
| `unsupported` | A required capability cannot be reproduced | Leave untouched and record the missing capability |
| `orphaned-downstream-drift` | User-authored target content has no Claude source | Leave untouched pending a separate deletion or promotion decision |

Treat custom slash-workflow behavior as portable by default. Use `unsupported` only after verifying that the target cannot reproduce a required capability. An ambiguous collision is `blocked`; it does not block independent items.

Before previewing an `adaptation`, render its complete target-native bytes into a safe local staging path outside every source and target setup root. Record the staged path, content checksum, target format, and exact semantic delta from the unchanged Claude source. A failed or ambiguous rendering is `blocked`, not a future write-time decision.

Resolve the proposed backup without creating it: resolve every existing symlink component through the nearest existing ancestor, append any missing path components, and normalize the result. Require both the proposed path and resolved physical path to be outside every Claude-visible source root, resolved source root, target setup root, and resolved target root. A path equal to or beneath any such root is `blocked`. Record the resolved backup path and use only that path in confirmation, preflight, backup creation, the backup manifest, and recovery actions.

Render a manifest before any write:

```markdown
### Setup sync manifest

- **Claude source roots:** <active Claude-visible roots>
- **Detected targets:** <agent and setup roots>
- **Excluded surfaces:** <surface and reason>
- **Proposed backup:** <timestamped path> → <resolved physical path>

| ID | Target | Kind | Claude-visible source | Resolved source | Source checksum | Target path | Existing kind / checksum | Classification | Link target or staged path / checksum | Semantic delta | Planned action | Status / reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
```

For an exact copy, record both the proposed link target and resolved physical source. Assign one pre-confirmation status to every item:

- `ready`: the exact link target is resolved, or the adaptation's final bytes are staged and checksummed;
- `blocked`: a collision, incomplete classification, or unstaged adaptation prevents a safe write;
- `preserved-unsupported`: the target cannot reproduce required behavior; or
- `preserved-orphaned`: downstream-only user content remains untouched.

Summarize per target. List item counts by classification, paths to change, unsupported behavior, orphaned drift, collisions, and acceptance surfaces. An exact-copy symlink shares physical content. Editing through the downstream path also changes Claude's source, so authority stays procedural rather than filesystem-isolated.

**Gate.** the manifest accounts for the full in-scope Claude inventory and all detected downstream user-authored artifacts, every adaptation's final bytes and semantic delta are previewable, and every item has exactly one status without proposing any import or deletion.
