# Official Source Runtime Contract

## Purpose

Provide a shared runtime boundary for official career source adapters.

Adapters provide factual job source records only.

The executable reference implementation is [job_source_runtime.py](../scripts/job_source_runtime.py). Current live coverage includes SAP discovery/detail, Tencent detail verification, and Kuaishou social-recruitment discovery/detail.

## Input

- company
- career_url
- optional external_job_id

## Output

- company
- role
- location
- department
- source_url
- external_job_id
- captured_at
- verification_status

## Status

- OPEN_VERIFIED
- NEEDS_VERIFY
- CLOSED

## Boundary

Runtime does not produce:

- fit assessment
- ranking
- application decision
