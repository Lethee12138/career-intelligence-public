# Career Intelligence

Career Intelligence is a Skill + MCP toolkit that helps AI agents perform career research, job discovery, role analysis, and application preparation.

This public repository contains the reusable capability layer and synthetic demonstrations. It does not contain a real person's Career records, CV sources, application history, private preferences, live scan results or conversation provenance.

## Supported usage

Career Intelligence is designed for:

- Codex and other AI agents supporting Skills
- MCP-compatible clients using the Career Intelligence MCP server

Support depends on each client's Skill and MCP implementation.

## What it provides

- evidence-first role and JD analysis
- output-first and capability-first discovery through Capability → Role Family → Market Title mappings
- AI-neutral discovery across AI-core, AI-enabled and non-AI-but-fit work
- bounded job discovery and routing
- MCP `career.scan_and_review` modes: `configured_review`, `market_discovery`, and `hybrid_discovery`
- external Web discovery handoff and standardized candidate-only result ingest
- configurable Market Discovery profiles with neutral public defaults
- result-set coverage safeguards for over-concentrated discovery batches
- structured `why_matched` explanations with evidence references
- job quality and market-calibration contracts
- work-right, sponsorship and work-territory checks
- application-preparation review boundaries
- a read-only local MCP service and standard-library guards

## Quick start

Start with [QUICKSTART.md](QUICKSTART.md). MCP details are in [mcp/job-scanner-contract.md](mcp/job-scanner-contract.md). The public demo is in [tests/fixtures](tests/fixtures) and [tests/outputs/public-demo-review.md](tests/outputs/public-demo-review.md).

## Privacy boundary

Users provide their own private Career context at runtime. Keep personal evidence, CVs, preference profiles, work-right records, application records, credentials, local paths and conversation IDs outside this repository. Historical private regression material is not part of this public release workspace.

## External action boundary

The toolkit produces review candidates and handoffs. It does not submit applications, contact employers, log in, upload files, modify a user's Career records or silently create evidence. Human review remains required before any external action.

## Generic Market Discovery

Dedicated company adapters are optional source and verification accelerators; they are not the discoverable-market boundary. `market_discovery` returns `HANDOFF_REQUIRED` with `EXTERNAL_WEB_DISCOVERY_HANDOFF` when no candidates are supplied. A read-only Web-capable host can discover public leads, prefer official Careers/ATS pages, then return standardized candidates through `career.scan_and_review.discovery.candidates`. The runtime reports `builtInWebDiscovery=false` and never pretends it browsed.

Public defaults are neutral on company size, big-tech status, familiar brands and adapter availability. Callers can provide a private `careerContext.market_discovery_profile`; the public default contains no personal priorities and the example is synthetic. The coverage safeguard evaluates only the returned result set. It does not claim that the real market has a particular distribution.

## License

No open-source license is selected in this release workspace yet. Add a license before inviting downstream redistribution.
