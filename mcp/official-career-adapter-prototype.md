# Official Career Adapter Prototype

## Purpose

Convert official company career pages into verified Job Source Records.

This adapter provides evidence only.
It does not decide candidate fit or application priority.

## Input

- company career URL
- company identity
- optional job identifier

## Extraction

Collect:

- company
- role title
- location
- department
- job URL
- external job ID
- requirements
- responsibilities
- application status indicators

## Verification

Output:

- OPEN_VERIFIED
- NEEDS_VERIFY
- CLOSED

Authority:

Official career sources are HIGH authority.

## Boundary

The adapter must not:

- rank candidates
- recommend application
- modify CV
- submit applications
