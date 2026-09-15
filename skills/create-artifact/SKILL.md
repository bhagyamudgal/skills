---
name: create-artifact
description: Publish an HTML or Markdown report to Folslate and return a public fol.ink URL. Prefer HTML over Markdown. Use when sharing plans, reports, audits, findings, or other user-facing material as a link, or when output is too long to paste inline.
---

# Create artifact

Folslate hosts one HTML or Markdown file at a public URL. I publish the
report there and hand back the link. I default to HTML for every report and
fall back to Markdown only for plain text with no tables, charts, or custom
styling.

For the raw HTTP behind the upload, load the `folslate-api` skill. For every
CLI command and flag, load the `folslate-cli` skill.

## Check these before uploading

None of the three can be undone after the upload, so I read them as a
checklist and confirm each one holds for this exact document.

**The link is public.** Anyone holding the URL reads the document, with no
authentication, and it cannot be unpublished. I keep credentials, keys,
customer records, and anything the user has not agreed to publish out of the
upload.

**It expires in one day, unless I publish signed in.** An anonymous upload
answers `404` after a day. A signed-in upload is permanent and answers
`expires: null`, which is what I use for plans the user must open later.

**The page is inert.** A hosted document cannot run JavaScript, load an
external stylesheet, font, or image, submit a form, or be framed. A report
that pulls a chart library from a CDN renders as a blank page, so I inline
`<style>` and `data:` images instead. Markdown escapes raw HTML rather than
passing it through, which is why HTML is the default.

## Publish

First I check whether the CLI is there and signed in. Signed in means the
upload is permanent; anything else means it expires in a day:

```bash
folslate --version
folslate auth status
```

A signed-in CLI publishes a permanent link:

```bash
folslate upload page.html --title "Release notes"
```

Signed out, the same command still works: the upload is anonymous and the
link dies in a day. Only when the binary itself is missing do I install it,
then publish with it:

```bash
t=$(mktemp /tmp/folslate-install.XXXXXX) && curl -fsSL https://folslate.com/install.sh -o "$t" && sh "$t" && folslate upload page.html --title "Release notes"
```

Where installation itself fails, I fall back to an anonymous upload, and I
say plainly that the link dies in a day:

```bash
curl -sS -X POST https://api.folslate.com/v1/upload \
  -H 'content-type: text/html' \
  -H 'x-folslate-title: Release notes' \
  --data-binary @page.html
```

I use `--data-binary`, never `-d`. `-d` strips newlines and collapses the
whole file into one paragraph, which destroys Markdown.

A `201` carries `data.url` and `data.expires` (or `expires: null` for a
permanent document). I report both together, because a link without its
expiry reads as permanent and an anonymous one is not. An anonymous upload
also returns an `ownership` secret, shown once: I save it beside the link
only when the document may need updating, and I never send it to anyone but
`api.folslate.com`.

## When it fails

I branch on the status and on `error.code`, never on prose. Over 1 MB I split
or trim the document (`payload_too_large`). A wrong content type means
resending as `text/html` or `text/markdown` (`unsupported_media_type`).
`rate_limited` waits out `Retry-After`; `quota_exceeded` means the signed-in
account is over quota, so I read `error.details.resetsAt`, wait for the reset
or delete owned documents, and never blind-retry; `storage_unavailable`
retries once,
knowing a retried upload mints a new document. `not_found` on a read means
expired or never existed, so I do not retry.
