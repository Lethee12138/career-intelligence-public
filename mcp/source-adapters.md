# Job Scanner Source Adapter Design

## Purpose

Source adapters connect public job sources to Job Scanner MCP.

Adapters collect and normalize information.
They do not make career decisions.

## Common Interface

Each adapter provides:

- adapter_name
- source_type
- authority_level
- supported_actions

Supported actions:

- discover
- extract
- verify

## Adapter Types

### Official Career Adapter

Source:
- company career pages
- official recruitment systems
- official campus pages

Authority:
HIGH

Actions:
- discover jobs
- extract JD data
- verify status

## Campus Recruitment Adapter

Source:
- graduate programs
- university recruitment pages

Extra fields:

- graduation_requirement
- application_window
- degree_requirement

## Public Job Page Adapter

Source:
- public job boards
- public professional networks

Authority:
MEDIUM or LOW

Usage:
- discovery
- lead generation

Official verification is required before adoption.

## Identity Resolution

Duplicate checks use:

1. official job ID
2. official URL
3. company + role + location + time

Results:

- NEW
- EXACT_DUPLICATE
- POSSIBLE_DUPLICATE


# Official Career Adapter Prototype

## Purpose

Read publicly available official career pages and transform verified job information into Job Source Records.

## Authority

Default authority level:

HIGH

## Supported Actions

- discover
- extract
- verify

## Verification Requirements

Before OPEN_VERIFIED:

- official company domain confirmed
- job page accessible
- role identity captured
- location captured

## Examples

Supported future adapters:

- Tencent Career
- Kuaishou Career
- ByteDance Career
- SAP Career
- Schneider Career

The adapter does not decide candidate fit or application priority.
