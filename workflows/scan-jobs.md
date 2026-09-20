# /scan-jobs

## Purpose

Discover currently available public job opportunities and create review candidates.

This workflow extends Career Intelligence from reactive job analysis to bounded market discovery.

It does not:

- apply for jobs
- log in to recruitment systems
- upload materials
- contact recruiters
- modify Career canonical records

## Inputs

Required runtime context:

- current configured source preset
- current read-only Career context provider
- Capability / Evidence / Preference / Job Quality references reachable from current Career context

Optional request overlay:

- `poolMode = BROAD | FOCUSED`
- bounded Career-context clarifications that do not replace current exact-role continuity

For the ChatGPT MCP surface, source adapters, URLs, queries and limits are not caller inputs.

## Process

1. Freeze the configured source scope before discovery. Compute/retain its source-scope identity. `BROAD` / `FOCUSED` never modifies adapters, URLs, queries, locations or limits.
2. Load the current read-only Career context provider before exact-role continuity. A request overlay may add or update matching role facts but cannot silently remove existing exact roles.
3. Discover the bounded configured public job sources; discovery-only leads remain `NEEDS_VERIFY`.
4. Normalize source facts through the [official source runtime](../mcp/official-source-runtime.md) when an official adapter is available.
5. Verify source and vacancy status. The standard-library [job source runtime](../scripts/job_source_runtime.py) is the executable source boundary for supported public sources.
6. Combine supported sources with the [multi-source scan batch](../scripts/job_scan_batch.py), deduplicate by stable source identity / official job ID, and preserve failed verification as `NEEDS_VERIFY` rather than inventing closure.
7. Apply transparent first-pass screening signals only:
   - location preference signal
   - role-family term signal
   - capability-language signal
   - explicit preference-risk terms
   - visible student / graduate / experience requirements
   - Job Quality remains UNKNOWN unless the vacancy itself supplies relevant evidence
8. Career Intelligence then assesses:
   - Eligibility Fit
   - Capability Fit
   - Preference Fit
   - Job Quality
   - Interview Process Risk
9. Build exact-role review packets with the [scan review bridge](../scripts/job_scan_review_bridge.py). Existing exact roles become continuity packets rather than duplicates; visible internship/experience/language/quant gates are surfaced before high-effort analysis.
10. Build the requested post-discovery pool view: `BROAD` retains more discovered candidates for layered review; `FOCUSED` keeps the higher-priority review set. The source-scope fingerprint MUST remain identical across pool modes.
11. Send only bounded new candidates into `/analyse-job`; roles already in the Application Pool reuse their existing state. Route only after Career Intelligence review.

## Output

Return a deduplicated Candidate Pool. The batch runtime may add non-final screening states:

- REVIEW_PRIORITY
- REVIEW
- VERIFY
- DEPRIORITIZE
- CLOSE

These are triage states, not final Fit or application decisions. The downstream review bridge emits `EXISTING_POOL_CONTINUITY`, `SOURCE_VERIFY_FIRST`, `QUALIFICATION_REVIEW_REQUIRED` or `READY_FOR_JOB_ANALYSIS`; none is an application authorization.

Allowed Career Intelligence routes:

- OPPORTUNITY_POOL
- FAST_LANE
- TARGETED_PREPARE
- WATCH
- CLOSE
