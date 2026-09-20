# SAP Career Adapter Prototype

## Purpose

First real-source adapter candidate.

The adapter validates the official career source flow before scaling to other companies.

## Scope

Input:
- official SAP career URL
- optional job identifier

Output:
- Job Source Record
- verification status

## Extraction

Collect only factual fields:
- company
- role title
- location
- department
- job URL
- external identifier
- requirements
- responsibilities

## Verification

Allowed:
- OPEN_VERIFIED
- NEEDS_VERIFY
- CLOSED

## Boundary

The adapter does not calculate:
- capability fit
- preference fit
- application priority

Career Intelligence performs those decisions after extraction.
