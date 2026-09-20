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
- output-first and capability-first discovery
- bounded job discovery and routing
- job quality and market-calibration contracts
- work-right, sponsorship and work-territory checks
- application-preparation review boundaries
- a read-only local MCP service and standard-library guards

## Quick start

Start with [QUICKSTART.md](QUICKSTART.md). The public demo is in [tests/fixtures](tests/fixtures) and [tests/outputs/public-demo-review.md](tests/outputs/public-demo-review.md).

## Privacy boundary

Users provide their own private Career context at runtime. Keep personal evidence, CVs, preference profiles, work-right records, application records, credentials, local paths and conversation IDs outside this repository. Historical private regression material is not part of this public release workspace.

## External action boundary

The toolkit produces review candidates and handoffs. It does not submit applications, contact employers, log in, upload files, modify a user's Career records or silently create evidence. Human review remains required before any external action.

## License

No open-source license is selected in this release workspace yet. Add a license before inviting downstream redistribution.
