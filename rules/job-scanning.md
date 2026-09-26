# Job Scanning Rules

## Evidence First

A discovered vacancy is a lead, not evidence of suitability.

## Brand Neutrality

Company reputation must not replace role analysis.

## Title Neutrality

Job titles do not determine actual work.

Examples:

- Product Consultant may include sales responsibility.
- Digital Transformation may include implementation delivery.

## AI Neutrality

AI keywords do not automatically increase fit.

Assess:

- workflow design
- user problem understanding
- product decision
- experimentation
- human-AI interaction

## Preference Protection

Flag:

- sales quota
- customer acquisition
- business development
- aggressive commercial targets

Do not automatically reject:

- stakeholder communication
- user interviews
- cross-functional collaboration

## Source-scope immutability

For the ChatGPT MCP path, the configured source preset is authoritative for a scan run. The caller cannot replace adapters, widen queries, change URLs, or raise limits through `career.scan_and_review`.

`BROAD` and `FOCUSED` are post-discovery retention/display modes only. A pool-mode choice must never change the source-scope fingerprint or trigger additional discovery. If broader source coverage is desired, that is a separate Human-reviewed source-configuration change.

## Current Career context

Exact-role continuity and stable preferences come from the local read-only Career context provider. Do not reconstruct current role state from chat memory when the provider is available. Request overlays may add or clarify facts but cannot silently delete existing exact roles. Missing provider state is an execution error, not permission to guess.

## First-pass screening boundary

The multi-source batch may triage verified and unverified vacancies for review. It must not fabricate a fit percentage or treat keyword matching as a final assessment.

- `REVIEW_PRIORITY` means several configured scan signals are present.
- `DEPRIORITIZE` is reversible and must preserve the exact reason.
- `VERIFY` means source/status uncertainty comes first.
- Explicit experience requirements may be surfaced as a gap signal only against a configured early-career bound.
- Job Quality stays `UNKNOWN` when the public vacancy does not establish pay, workload, leave, management quality, or stability.

## External Action Boundary

Scanning creates candidates only. Human review remains required before application actions.

## Generic discovery and coverage

Source-scope immutability applies to `configured_review`. In `market_discovery` and `hybrid_discovery`, a generic external-Web handoff may add standardized candidates from companies without dedicated adapters. Adapter availability never sets the market boundary. External candidates enter as `NEEDS_VERIFY` with `VERIFY_OFFICIAL_SOURCE` unless exact official-source checks are supplied.

The public neutral profile may detect concentration in the returned result set. `UNKNOWN` buckets do not count as verified coverage. A market-evidence override requires explicit evidence refs, and one completed supplement pass prevents repeated supplement requests.
