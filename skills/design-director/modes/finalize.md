# Mode — Finalize Identity

- **Inputs**: the approved selection record, editable source artwork, or a deterministic construction spec. If none exists, return to `logo` stage `select`. If more than one version could be final, ask the user to identify it before continuing.
- **Slots**:
  1. Approved version or source
  2. Requested asset units, theme variants, formats, and sizes
  3. Output directory

  Fill these from the thread or repository. When unspecified, default the asset units to mark, wordmark, primary horizontal lockup, and stacked lockup; theme variants to light, dark, and automatic; and formats to SVG and PNG. Default the output directory to `design/brand-final/` only after echoing it. If the user has not supplied or established a path, ask once before writing there. Do not re-ask whether to save.

## Lifecycle

1. **Lock the selection.** Record the approved source, geometry, colors, typography, lockup order, and any final delta. If the user only approved a direction and did not request files, present this selection record, offer the production package, and stop.
2. **Freeze the matrix.** Echo the asset units, theme variants, formats, sizes, and output directory before writing. An explicit export, package, asset, or save request authorizes the listed local files, not additional applications or remote writes. Full finalization requires retained SVG masters. When the user excludes SVG, ask whether to add it or perform a partial raster export and label finalization incomplete.
3. **Build native masters.** Use or construct a deterministic vector source. Write master SVG files only when the frozen matrix includes SVG. A partial PNG-only export requires an existing deterministic vector source and retains no unrequested SVG. Image generation may inform exploration, but a generated bitmap is not a final logo master. Include outlined wordmark vectors in a full finalization. Record the editable font source, license, and the date its terms were checked, or identify the wordmark as custom-drawn.
4. **Build theme and size variants.** Produce only the asset × theme × format combinations in the frozen matrix. Explicit light or dark SVGs and transparent PNGs use the requested sizes. When sizes are absent, use 16, 24, 32, 48, 64, 128, 256, and 512 px for the mark, and 256, 512, and 1024 px for each lockup or wordmark. An automatic variant is SVG-only and switches with `prefers-color-scheme`; resolve an automatic-plus-PNG request before building because a PNG cannot switch at runtime. Create a compact mark when the master loses detail, and record its switch size.
5. **Validate the rendered assets.** Treat every check below as blocking. Repair failures before packaging.
6. **Package the verified files.** Add a concise usage guide, a manifest that enumerates the frozen asset × theme × format × size matrix, SHA-256 checksums, and a ZIP. Re-open the ZIP and compare its inventory and file digests with the manifest.
7. **Apply explicit cleanup.** Retain iterations by default. When cleanup was requested, inventory the exact superseded paths, state the recovery method, and obtain approval for that list before deleting. Preserve the approved source and every final deliverable. After deletion, re-run the preserved-file inventory and checksums, then report the removed paths and whether they remain recoverable.
8. **Hand off.** Print the final directory, asset counts by format and theme, minimum sizes, validation results, checksum path, ZIP path, and any evidence ceiling.

## Blocking validation

- Parse every SVG. Verify every PNG's dimensions and transparency.
- Render each explicit theme variant on its intended background. Render the automatic SVG under both light and dark media conditions and verify that it switches to the expected colors.
- Inspect the mark and responsive mark at actual size. Verify the declared minimum size and switch point.
- Verify every lockup against the recorded element order, clear space, and alignment.
- Classify each contrast use and apply the WCAG 2.2 criteria in the main skill. Give logotypes a measured brand-use legibility result rather than a WCAG pass.
- Record visual collision screening as `completed` or `unavailable`. A completed screen includes the deliberate divergence moves and legal-clearance caveat. An unavailable screen leaves originality unverified and must appear in the handoff's evidence ceiling.
- Compare the generated inventory with the frozen matrix. Missing or extra asset, theme, format, or size combinations fail validation.
- Mark the handoff incomplete when the user chose a partial raster export without retained SVG masters.

- **File save**: yes
- **Next step**: none
