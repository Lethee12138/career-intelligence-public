# Discovery Candidate Schema

## Identity

- company
- role
- location

## Discovery Source

- source_url
- source_type
- captured_at

## Status

Initial state:

DISCOVERED

Possible transitions:

- NEEDS_VERIFY
- VERIFIED
- CLOSED

## Boundary

Discovery Candidate is not:

- a confirmed opening
- an application target
- a fit assessment

Verification must happen before Job Source Record creation.
