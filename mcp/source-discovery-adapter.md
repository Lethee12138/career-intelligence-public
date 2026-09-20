# Public Discovery Adapter Design

## Purpose

Discover possible job opportunities from public sources.

Discovery results are leads, not verified openings.

## Source Types

- official public vacancy search endpoints
- public search results
- public job aggregators
- public professional platforms

## Live executor coverage

The current standard-library runtime supports live official discovery for SAP search pages and Kuaishou social-recruitment public APIs. Tencent official detail verification is live, while broad Tencent discovery remains pending. Third-party discovery stays a lead until official verification.

## Output

Creates:

Discovery Candidate

Fields:

- company
- role
- location
- source_url
- captured_at
- source_type

## Boundary

Discovery Adapter does not:

- confirm final availability
- assess personal fit
- rank companies
- submit applications

Flow:

Discovery Candidate

↓

Source Verification

↓

Job Source Record

↓

Job Scan Candidate
