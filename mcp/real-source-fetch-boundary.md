# Real Source Fetch Boundary

## Purpose

Define the boundary before connecting live official career pages.

## Flow

Official Career URL

-> Fetch Layer

-> Extraction Layer

-> Official Source Runtime

-> Job Source Record

-> Verification

## Fetch Layer

Responsible for:

- retrieving public pages
- preserving source URL
- recording capture time
- returning raw source content

Not responsible for:

- career fit judgement
- ranking
- application decisions

## Extraction Layer

Responsible for:

- mapping page fields
- identifying job identifiers
- extracting title/location/requirements

Output must remain factual.

## Failure States

- PAGE_UNAVAILABLE
- STRUCTURE_CHANGED
- NEEDS_MANUAL_REVIEW
