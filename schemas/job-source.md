# Job Source Schema

## Source Identity

A job source records where information came from.

Fields:

- source_identity
- url
- source_type
- captured_at

## Source Type

Allowed values:

- official
- campus
- third_party
- unknown

## Verification

Fields:

- verification_method
- freshness
- authority_level

## Authority

Authority describes source reliability.

It does not determine candidate fit.
