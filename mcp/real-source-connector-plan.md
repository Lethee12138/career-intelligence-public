# Real Source Connector Plan

## Purpose

Define the first real source connection phase for Official Career Adapter.

The connector layer retrieves public job information only.

It does not:

- rank candidates
- decide applications
- submit applications

## Phase 1 Source Strategy

Start with one official career page.

Pipeline:

Official page

-> extraction

-> Job Source Record

-> verification

-> Job Scan Candidate

## Connector Output

Required fields:

- company
- role
- location
- source_url
- external_job_id
- captured_at
- status

## Verification

Unknown pages remain NEEDS_VERIFY.

Only verified official evidence can become OPEN_VERIFIED.
