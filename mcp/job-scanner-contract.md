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
- Private MCP HTTP surface: `mcp/career-mcp-http-server.mjs`
- Secure Tunnel helper: `scripts/career-mcp-tunnel.sh`

The MCP server binds only to `127.0.0.1:8797`. Tool execution is stateless and performs no Career-context writes, while current exact-role continuity is read from a private local context snapshot outside the repository through `scripts/career_context_provider.py`. Tunnel ID and runtime credentials remain external to the repository; Career must not reuse another workspace's tunnel ID, local MCP port, or credential file.

Input:

- `poolMode = BROAD | FOCUSED`
- optional request-scoped `careerContext` overlay
- `detailLevel = summary | review | full`

The current local Career context provider is always enabled on the public ChatGPT tool surface; callers cannot disable or replace it.

The public ChatGPT MCP surface deliberately does **not** expose `scanConfig`, source adapters, URLs, discovery queries or source limits. `BROAD` / `FOCUSED` can only change the post-discovery pool view. The output includes the immutable source scope/fingerprint and current Career-context source/version so callers can detect scope or continuity drift. Invalid runtime state returns a descriptive contract error; raw implementation exceptions are not part of the public contract.

Execution:

`public discovery → official verification → dedupe → transparent triage → exact-role review packets`

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
