# Official Career Adapter Runtime Prototype

## Purpose

Prototype the runtime boundary between official career sources and Career Intelligence.

The adapter provides verified source data only.

It does not make career decisions.

## Runtime Flow

Official Career Source

→ Adapter Extraction

→ Job Source Record

→ Verification

→ Job Scan Candidate

→ Career Assessment

## Supported Operations

### discover

Find candidate roles from an official career source.

### extract

Normalize role information into Job Source Record format.

### verify

Check source availability and status indicators.

## Output Boundary

Allowed:

- source identity
- job identity
- location
- role information
- verification status

Not allowed:

- candidate ranking
- application decision
- CV routing
- external action
