---
name: create-artifact
description: Upload a Markdown or HTML artifact to Folslate and return a public fol.ink URL. Use to share plans, reports, audits, findings, or other user-facing material as a link, when output is too long to paste inline, or when reading a fol.ink link.
---

# Create artifact

Folslate hosts one Markdown or HTML file at a public URL. There is no account and no token. I POST the bytes to `api.folslate.com` and get back a `fol.ink` link.

## Check these before uploading

None of the three can be undone after the upload, so I read them as a checklist, not a suggestion.

**The link is public.** Anyone holding the URL reads the document, with no authentication. Folslate has no delete, list, or edit endpoint, so I cannot revoke a link once I give it out. I keep credentials, keys, customer records, and anything the user has not agreed to publish out of the upload.

**It expires in one day.** The `201` carries the exact `expires` timestamp. I hand it to the user beside the link. After it, reads answer `404`.

**The page is inert.** A hosted document cannot run JavaScript, load an external stylesheet, font, or image, submit a form, or be framed. An HTML report that pulls a chart library from a CDN renders as a blank page. Folslate also strips every `<meta http-equiv>` and every `<noscript>` at upload.

What I can do instead depends on the upload type. A `text/html` upload keeps inline `<style>`, and images load as `data:` URIs, so I inline the SVG the CDN would have drawn. A `text/markdown` upload escapes raw HTML rather than passing it through, so an `<svg>` or `<style>` block written into Markdown arrives as visible text. Folslate styles Markdown itself, and a chart has to become a `data:` image.

## Upload

Immediately before any POST below, I invoke `preflight-mutations` for the exact artifact and Folslate target. Its mutation card must cover the document bytes, any sensitive material they contain, the public one-day retention, and the absence of revocation or deletion. Because this is an irreversible off-box publication, I let `preflight-mutations` decide whether the current authorization is fresh and exact enough. I continue only on `ready`. On `confirmation-required` I wait for the named confirmation. I re-check the card invalidators before sending.

```bash
curl -sS -X POST https://api.folslate.com/v1/upload \
  -H 'content-type: text/markdown' \
  --data-binary @report.md
```

I use `--data-binary`, never `-d`. `-d` strips newlines and collapses the whole file into one paragraph, which destroys Markdown.

The `content-type` is `text/markdown` or `text/html`. Folslate rejects every other value with `415`, and it decides the pipeline. A `text/markdown` body is converted to HTML and wrapped in a page shell, while a `text/html` body is sanitized and kept.

A `201` looks like this.

```json
{
    "success": true,
    "message": "Document stored",
    "data": {
        "url": "https://fol.ink/doc_01k3n8w5q2r7v0xyz4a6bcdefg",
        "expires": "2026-08-26T09:12:44.000Z",
        "title": "Quarterly report"
    },
    "error": null
}
```

I report `data.url` and `data.expires` together. A link without its expiry reads as permanent, and it is not.

## Read a document back

```bash
curl -sS -i https://fol.ink/doc_01k3n8w5q2r7v0xyz4a6bcdefg
```

A `200` with `Content-Type: text/html` returns the stored document. Failures use a non-`200` status and `Content-Type: application/json`, so I parse the JSON envelope only for that media type. When the status and media type disagree, I treat the response as unexpected instead of guessing from its first byte.

`curl -I` on the same URL tells me a link is alive without recording a view.

Ids are `doc_` followed by 26 lowercase Crockford Base32 characters, which exclude `i`, `l`, `o`, and `u`. I use the `url` the upload returned rather than building one.

## Titles

Every stored document carries a `<title>`. Folslate takes it from `X-Folslate-Title`, else the document own `<title>` or first heading, else the document id.

I run the upload preflight above for this exact HTML artifact before this POST.

```bash
curl -sS -X POST https://api.folslate.com/v1/upload \
  -H 'content-type: text/html' \
  -H 'x-folslate-title: Release notes' \
  --data-binary @page.html
```

The `201` echoes the title the document actually got, so I read `data.title` rather than fetching the document back to check. Folslate collapses whitespace and cuts the title at 200 characters, so a long one comes back changed.

A header value carries UTF-8 correctly from a CLI or an agent. Browser `fetch()` cannot reliably send a non-ASCII header, so in browser code I put the title in the document instead, where a Markdown `#` heading is read from the body as UTF-8.

## When it fails

Every response from `api.folslate.com`, and every failure on either host, has the same four fields, `success`, `message`, `data`, and `error`. `data` is `null` whenever `success` is `false`. I branch on `error.code`. The `message` is prose and gets reworded.

| `error.code`             | Status | What to do                                                                                                       |
| ------------------------ | ------ | ---------------------------------------------------------------------------------------------------------------- |
| `unsupported_media_type` | 415    | Send `text/markdown` or `text/html`. `error.accepts` lists them.                                                 |
| `payload_too_large`      | 413    | The body is over `error.maxBytes`. Split the document or trim it.                                                |
| `unprocessable_document` | 422    | Rendering failed. The same bytes fail the same way, so change them before retrying.                              |
| `rate_limited`           | 429    | Wait the `Retry-After` seconds, then retry.                                                                      |
| `storage_unavailable`    | 503    | Transient. Retry once.                                                                                           |
| `not_found`              | 404    | On a read: expired, never existed, or a malformed id. These are deliberately indistinguishable, so do not retry. |

## Limits

Max body is 1 MB. Uploads are rate limited per IP at 20 a minute, counted per Cloudflare location rather than globally, so I treat it as a brake on bulk traffic rather than an exact quota. Retention is one day from upload.
