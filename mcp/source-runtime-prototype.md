# Job Scanner Source Runtime Prototype

## Purpose

Define a testable runtime path from source adapters to job scan candidates.

This prototype uses synthetic sources first.

It does not perform external crawling, login, or application actions.

## Runtime Flow

Source Adapter

-> Job Source Record

-> Verification

-> Job Scan Candidate

-> Career Assessment

## Prototype Adapter Types

- official_career_mock
- campus_recruitment_mock
- third_party_mock

## Required Checks

- source identity exists
- source type is preserved
- authority level is preserved
- job status is not invented
