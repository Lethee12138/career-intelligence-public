# Career Intelligence Quick Start

## Public repository boundary

This public repository contains only the capability layer and synthetic examples. Users provide their own private Career context at runtime. Personal Career data, CV sources, preference profiles, work-right records, application history, credentials and local provenance should remain outside the repository.

## What you need

- a compatible MCP client or Codex-like Skill host
- Node.js for the local MCP service
- your own private context provider or caller-supplied context

The repository does not include a personal context snapshot or a personal job-scan preset.

## Basic flow

1. Install or load the Skill in your client.
2. Start the local MCP service if your client uses MCP.
3. Supply private candidate context through the client's supported external context mechanism.
4. Supply a Capability Profile / Role Hypothesis input, or a caller-owned configured source set, when discovery is requested.
5. Review facts, evidence, gaps, eligibility, quality and VERIFY items before any external action.

## MCP discovery modes

The single user-facing MCP tool is `career.scan_and_review`:

- `configured_review` keeps the caller's configured source policy.
- `market_discovery` builds a Search Execution `0.2.4` handoff from supplied Capability Profile / Role Hypotheses and discovery candidates.
- `hybrid_discovery` combines configured candidates with discovery candidates and deduplicates them.

Discovery candidates are leads requiring official-source verification. Each visible candidate carries `role_family`, `ai_involvement`, structured `why_matched`, `evidence_refs`, `risk` and `next_action`. AI capability does not imply an AI-only search: the taxonomy keeps AI-core, AI-enabled and non-AI-but-fit families in view.

Example request shape (synthetic values only):

```json
{
  "mode": "market_discovery",
  "discovery": {
    "roleHypotheses": [{"id": "SYN-H1", "role_or_family": "Product"}],
    "capabilityProfile": {"capabilities": ["SYN-CAPABILITY"]},
    "candidates": [{"company": "Example Org", "role": "Product Manager", "role_family": "PRODUCT"}]
  }
}
```

This example is a bounded discovery input, not a vacancy or application recommendation.

## Start the local service

```bash
./scripts/career-mcp-service.sh install
./scripts/career-mcp-service.sh status
```

The service is local and read-only with respect to Career records. It does not make the public repository a place to store personal data.

## Synthetic demo

The demo files use `SYN-*` identifiers, fictional project names and `example.invalid` URLs:

- [candidate](tests/fixtures/public-demo-candidate.json)
- [job](tests/fixtures/public-demo-job.json)
- [evidence](tests/fixtures/public-demo-evidence.json)
- [market context](tests/fixtures/public-demo-market.json)
- [readable review](tests/outputs/public-demo-review.md)

These files are demonstrations only and must never be treated as a real candidate profile or a current vacancy.

## Caller-supplied scan configuration

The private current job-scan preset is intentionally absent. For a controlled demo or real use, pass a caller-owned configuration and private context explicitly, for example:

```bash
python3 scripts/career_scan.py \
  --no-configured-sources \
  --no-current-career-context \
  --scan-config /path/to/private-or-demo-scan-config.json \
  --career-context /path/to/private-context.json
```

Keep those files outside the public repository.

## Validation

```bash
python3 -I -S -B scripts/validate.py
python3 -B -m unittest discover -s tests -p 'test_public_*.py'
```

## Boundaries

No application submission, recruiter contact, login, upload, automatic monitoring, CV-source modification or Career-record write is performed by this toolkit.

## Two-stage Market Discovery examples

First call, with no company list and no candidates:

```json
{"mode":"market_discovery","discovery":{"roleHypotheses":[{"id":"SYN-H1","role_or_family":"Product"}],"marketScope":["SYNTHETIC_MARKET"]}}
```

Expected: `HANDOFF_REQUIRED` with `EXTERNAL_WEB_DISCOVERY_HANDOFF`. After a read-only external executor checks public sources, candidate-only ingest is valid:

```json
{"mode":"market_discovery","discovery":{"provider":"EXTERNAL_WEB_DISCOVERY_HANDOFF","candidates":[{"company":"Example MidTech","exact_role":"Digital Product Associate","company_coverage_bucket":"MID_LARGE_TECH","official_source":{"url":"https://example.invalid/jobs/syn-1","exact_role_verified":false},"live_status":"VERIFY"}]}}
```

Expected: `RESULTS_INGESTED`; unverified leads retain `NEEDS_VERIFY` and `VERIFY_OFFICIAL_SOURCE`. Older clients may send the compatibility envelope:

```json
{"scanConfig":{"mode":"market_discovery","discovery":{"roleHypotheses":[{"id":"SYN-H1","role_or_family":"Product"}]}}}
```

Pass caller-specific values under `careerContext.market_discovery_profile`; keep them outside this repository. See `schemas/market-discovery-profile.md` and the synthetic `references/market-discovery-profile.example.json`.

If a known-bucket result set exceeds the configured head-bucket threshold and supplement buckets are missing, current candidates are kept and the response adds `DISCOVERY_COVERAGE_IMBALANCE` / `SUPPLEMENT_REQUIRED`. Return `providerRun.coverage_supplement_pass=true` after one same-scope supplement to stop repetition. A concentration override requires both `head_concentration_supported=true` and non-empty evidence refs.
