# Domain verification

Use an evidence ladder: registry lookup for fast filtering, then registrar evidence
for finalists. A missing DNS record, blank website, timeout, or generic request
failure never proves availability.

## Status vocabulary

| Status | Meaning |
|---|---|
| `registered` | Registry RDAP returned a valid domain object |
| `candidate_available_rdap` | Exact registry RDAP lookup returned HTTP `404` with no domain object; registrar confirmation is still required |
| `registrar_confirmed_available` | Registrar visibly offers the exact domain at standard registration price |
| `premium_or_reserved` | Registrar labels it premium, aftermarket, reserved, or make-offer |
| `invalid_candidate` | The supplied spelling cannot map unambiguously to one valid `.com` label |
| `unknown` | Timeout, throttle, CAPTCHA, malformed response, unsupported TLD, or conflicting evidence |

Every result records the exact domain, status, UTC check time, method, a public
source URL or redacted endpoint identifier, response/result class, and error when
present. Never record query strings, credentials, session tokens, or client IPs.
Registrar results additionally record currency, first-year price, renewal price
when shown, and premium label.

## 1. Derive and normalize the domain

- For a display name, lowercase it and remove styling spaces between valid label
  characters: `Vids Jar` becomes `vidsjar.com`.
- Do not silently remove meaningful punctuation, transliterate letters, respell the
  name, add a prefix, or choose among ambiguous labels. Record `invalid_candidate`
  and request an explicit domain spelling instead.
- Lowercase and deduplicate exact fully qualified domains.
- Convert internationalized names to ASCII A-label/punycode before lookup.
- Record malformed labels, schemes, paths, ports, and credentials as
  `invalid_candidate`; do not query them.
- Check the exact `.com`; do not substitute prefixes, hyphens, or other TLDs.

## 2. Filter with registry RDAP

Discover the authoritative RDAP base through the
[IANA DNS bootstrap](https://www.iana.org/assignments/rdap-dns/rdap-dns.xhtml).
For `.com`, Verisign currently documents its registration-data service at
`https://rdap.verisign.com/com/v1/domain/<fqdn>`.

Interpret responses narrowly:

- valid `200` domain object -> `registered`;
- HTTP `404` with no domain object -> `candidate_available_rdap`, including a
  conforming structured RDAP error body;
- `429` -> honor `Retry-After`, reduce concurrency, then retry once;
- `400`, `401`, `403`, `5xx`, timeout, HTML, or malformed JSON -> `unknown`.

Start with at most five concurrent lookups, cache duplicate queries for the run,
and back off on throttling. A registry `404` can still represent a reserved,
blocked, or premium name at the registrar.

DNS may reject obvious delegated names before RDAP, but NXDOMAIN/NODATA never
advances a name to an available state. Use WHOIS only as a low-volume diagnostic
for ambiguous evidence, not as a bulk checker.

## 3. Confirm at a registrar

Use the user's named registrar. Otherwise use Namecheap's visible domain search.
When configured credentials already exist, documented registrar APIs may replace
the browser. Namecheap's `namecheap.domains.check` accepts up to 50 comma-separated
domains and exposes availability plus premium pricing, but ordinary registration
pricing requires separate evidence such as its documented pricing API. Redact all
credential-bearing request URLs.

Confirm all of these before assigning `registrar_confirmed_available`:

- the result is for the exact `.com`;
- it is offered for standard registration, not make-offer or aftermarket sale;
- no premium or reserved label appears;
- a standard first-year price is established by the registrar;
- in a browser, a registration action is visible; with an API, documented
  availability and pricing responses agree.

Capture a page snapshot or exact visible text when browser tools permit. Do not
click the registration action, add to cart, sign in, make an offer, or purchase.

## Opportunistic accelerators

An undocumented endpoint observed in an already-working browser session may
accelerate a large batch, but it never replaces the evidence ladder. Treat session
tokens such as Revved `rcs` values as ephemeral: do not store or replay them across
sessions, bypass anti-bot controls, or depend on their response schema. Confirm
every survivor through registry RDAP and the registrar.

## Final evidence

Recheck the chosen domain at the registrar immediately before the user acts.
Phrase the claim as "registrar-confirmed available at <time>", never "secured" or
"owned". Availability is a snapshot; only a successful registration can prove
acquisition.
