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
4. Supply a current role or a caller-owned scan configuration when discovery is requested.
5. Review facts, evidence, gaps, eligibility, quality and VERIFY items before any external action.

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
