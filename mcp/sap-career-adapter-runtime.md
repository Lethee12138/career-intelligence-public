# SAP Career Adapter Runtime

## Purpose

Validate a real official career source through the generic official source runtime.

## Flow

SAP Career URL

→ fetch source

→ extract job fields

→ create Job Source Record

→ verify status

→ pass to Career Intelligence

## Output

Required:

- company
- role
- location
- source_url
- external_job_id
- captured_at
- verification_status

## Boundary

This adapter provides source facts only.

It does not decide:

- capability fit
- preference fit
- application priority
- external application action
