# Ticket Evidence Preservation

Use this contract whenever you rewrite a ticket, split it, supersede it, or spin out follow-up issues. The calling skill owns ticket decisions, mutation preflight, and writes. This reference owns provenance and closeout evidence.

## Build the source map

Walk the issue body, comments, and attachments oldest first. Keep every item that bears on a requirement or finding. Leave unrelated discussion out.

Assign each retained item a stable `E<n>` ID and record:

- the normalized requirement or finding it supports;
- an exact excerpt, author, date, and direct body or comment URL;
- for an image, the exact Markdown attachment line and scoped surrounding excerpt, original attachment URL, source body or comment URL, and SHA-256 of the downloaded bytes;
- supersession or dependency links to other evidence IDs.

A summary can interpret this record. It never replaces it. An image description can aid search. It never stands in for the image bytes.

## Preserve images

Open every downloaded image during intake. Before you reuse its original attachment URL, check that the intended successor readers can render it with their expected repository access.

When they cannot, upload the unchanged downloaded bytes to the successor and record the original URL, new URL, and both SHA-256 values. The checksums must match before the successor is considered complete.

## Write the provenance graph

The original issue remains the authoritative provenance record even when it closes. Give it an `Investigation and successors` section containing:

- the complete investigation, keyed to every relevant evidence ID;
- the audit or investigation revision and date;
- an explicit statement that this issue is the authoritative provenance record;
- links to every successor and what scope moved to each.

Each successor contains only the evidence IDs relevant to its scope. It says `Split from #<n>`, preserves those IDs' excerpts, authors, dates, direct source URLs, and image provenance, and links sibling successors only when their scopes depend on one another.

## Closeout gate

After the mutation batch lands, fetch the rendered original and every successor from GitHub. Reread each issue and open every referenced image. Compare the rendered set with the source map:

- every scoped evidence ID, exact excerpt, author, date, and source link is present;
- the original links every successor and declares its authority;
- every successor links its predecessor and each dependency-relevant sibling;
- each image renders for the intended readers and its downloaded bytes match the recorded SHA-256.

Repair and reread every omission before reporting preservation complete. Missing original provenance blocks closure; missing successor evidence leaves that successor explicitly incomplete until it is repaired and reread.
