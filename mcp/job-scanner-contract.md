# Job Scanner MCP Contract

## Purpose

Provide read-only public job discovery support for Career Intelligence.

The MCP layer retrieves and normalizes external job information.
Career Intelligence remains responsible for assessment and routing.

## Boundary

The MCP layer MUST NOT:

- decide candidate suitability
- rank jobs by company brand
- submit applications
- login to recruitment systems
- upload candidate materials

Human review remains required before external action.

## Core operations

### scan_and_review()

Purpose:

Provide the ChatGPT/agent-facing high-level operation for one bounded scan cycle.

Reference implementation:

- Core orchestration: `scripts/career_scan.py`
- MCP HTTP surface: `mcp/career-mcp-http-server.mjs`
- Secure Tunnel helper: `scripts/career-mcp-tunnel.sh`

The MCP server binds only to `127.0.0.1:8797`. Tool execution is stateless and performs no Career-context writes. A caller may provide private context through its own read-only context provider; personal context, tunnel IDs and runtime credentials remain outside this repository.

Input:

- `mode = configured_review | market_discovery | hybrid_discovery` (default `hybrid_discovery`)
- `poolMode = BROAD | FOCUSED`
- optional request-scoped `careerContext` overlay
- optional `discovery` object with Capability Profile, Role Hypotheses, taxonomy reference, market/location scope, candidate constraints and supplied discovery candidates
- `detailLevel = summary | review | full`

The caller's context provider is read-only and remains outside this repository; a public package installation contains no personal context snapshot or source preset.

`configured_review` keeps caller-owned configured sources and does not widen source policy. `market_discovery` builds Search Execution `0.2.4` from supplied Capability Profile / Role Hypotheses and supplied candidates; it does not invent vacancies. `hybrid_discovery` combines configured candidates with discovery candidates and deduplicates them. `BROAD` / `FOCUSED` only change the post-discovery pool view. The output includes source scope, discovery mode and candidate explanation fields. Invalid runtime state returns a descriptive contract error; raw implementation exceptions are not part of the public contract.

Execution:

`configured/public discovery → Role Hypothesis handoff → official verification → dedupe → transparent triage → exact-role review packets`

Output:

- compact summary
- Candidate Pool
- review packets
- exact-role continuity markers
- qualification/source gates
- Human Review boundary

This operation MUST NOT turn triage into final Fit, persist Career state, edit CV/Portfolio materials or perform an application. MCP implementations should wrap the same Core logic rather than reimplementing a parallel scanner.

### search_public_jobs()

Purpose:

Discover publicly available job records.

Input examples:

- market
- location
- role family
- source preference
- time window

Output:

Unverified job leads only.

Required fields:

- company
- role
- location
- source_url
- source_type

### verify_job_source()

Purpose:

Check source authority and vacancy status.

Output:

- authority level
- captured time
- status

Allowed status:

- OPEN_VERIFIED
- NEEDS_VERIFY
- CLOSED

## Generic Market Discovery callable contract

Preferred callers use top-level `mode` and `discovery`. Older callers may use structured `scanConfig.mode` and `scanConfig.discovery`; conflicting values fail closed. `market_discovery` without candidates returns `HANDOFF_REQUIRED` for `EXTERNAL_WEB_DISCOVERY_HANDOFF`. Candidate-only result ingest is accepted. `hybrid_discovery` combines configured and generic candidates and deduplicates them. Dedicated adapters improve source verification and never define the market boundary.

`tools/list` exposes company, exact-role aliases, location, official source, live status, qualification facts, deadline/application rule, provenance, uncertainty, role family, AI involvement, `why_matched`, evidence refs, risk and company coverage bucket. A caller may provide `careerContext.market_discovery_profile`; the public package ships only neutral defaults and a synthetic example.
