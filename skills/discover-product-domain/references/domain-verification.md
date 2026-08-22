# Domain verification

Use an evidence ladder with two rungs: **screen** every candidate with a registry
lookup, then **confirm** the survivors at a registrar. A missing DNS record, blank
website, timeout, or generic request failure never proves availability.

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
Registrar results additionally record currency, standard first-year base price,
each mandatory fee, standard first-year total, renewal price when shown, and
premium label.

## Where the confirm rung carries the weight

`.com` has no registry premium tier. A premium `.com` is an aftermarket listing, which is a
registered domain, so it returns an RDAP domain object. An RDAP `404` on `.com` therefore
predicts standard registration price reliably.

New gTLDs do not behave that way. `.page`, `.ink` and their peers price short and dictionary
words at the registry, so an unregistered name can still cost many times the base rate. In a
2026 run `read.page` returned RDAP `404` and $1,091/yr at the registrar, and `drop.ink` returned
`404` and roughly $360/yr on renewal, while `inert.page` on the same TLD was standard-priced.
The pattern is that common words are premium and unusual ones are not.

Spend the confirm rung accordingly: screen `.com` in bulk and confirm only the finalists, and
confirm every new-gTLD candidate before recommending it.

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

## 2. Screen with registry RDAP

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

For a Namecheap API shortlist, partition the normalized, deduplicated domains into
batches of at most 50. Merge responses by exact normalized domain, map every
original supplied entry to exactly one evidence record, and never duplicate a
lookup result. After merging, assign `unknown` to every requested normalized
domain that lacks exactly one valid response, including omissions, malformed
entries, duplicates, and failed batches; do not omit it from the final accounting.

For standard `.com` pricing from `namecheap.users.getPricing`, use the one-year
`REGISTER` `RegularPrice` as the standard first-year base price. The effective
final `Price`, account-specific `YourPrice`, and coupon-specific `CouponPrice` may
be shown separately with those labels, but they never establish the standard
price. Add every unavoidable ICANN or registrar fee exposed separately from
`RegularPrice` to the displayed standard first-year total, recording each fee or
an explicit zero separately. Treat
`IsPremiumName=true`, a nonzero `PremiumRegistrationPrice`, or a nonzero `EapFee`
as `premium_or_reserved`. If any mandatory fee is unavailable or ambiguous, keep
the result `unknown` rather than assigning `registrar_confirmed_available`.

Confirm all of these before assigning `registrar_confirmed_available`:

- the result is for the exact `.com`;
- it is offered for standard registration, not make-offer or aftermarket sale;
- no premium or reserved label appears;
- the standard first-year base price, mandatory fees, and total are established
  by the registrar;
- in a browser, a registration action is visible; with an API, documented
  availability, premium, `RegularPrice`, and fee responses agree.

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
