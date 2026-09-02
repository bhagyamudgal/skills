# Apply and verify

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
