# Job Scan Candidate Schema

## Identity

- company
- role
- location
- department

## Source

- source_url
- source_type
  - official
  - campus
  - third_party
  - unknown

- captured_at

## Verification

job_status:

- OPEN_VERIFIED
- NEEDS_VERIFY
- CLOSED

## Assessment

Keep separate:

- eligibility_fit
- capability_fit
- preference_fit
- job_quality
- interview_process_risk

## Multi-source screening

Optional runtime fields:

- dedupe_identity
- duplicate_count
- screening.state
  - REVIEW_PRIORITY
  - REVIEW
  - VERIFY
  - DEPRIORITIZE
  - CLOSE
- screening.reasons
- screening.location
- screening.role_term_hits
- screening.capability_term_hits
- screening.preference_risk_hits
- screening.student_or_early_career_hits
- screening.experience_requirement
- screening.job_quality
  - default UNKNOWN unless supported by vacancy evidence
- screening.final_fit_decision = false

## Source scope and pool view

The ChatGPT MCP surface uses the configured source preset and exposes an immutable source-scope record:

- source_scope.immutable_for_pool_mode = true
- source_scope.sources
- source_scope.fingerprint

Pool mode is post-discovery only:

- pool_view.mode
  - BROAD
  - FOCUSED
- pool_view.retained_states
- pool_view.retained_candidate_count
- pool_view.candidate_keys
- pool_view.candidates
- pool_view.source_scope_changed = false

BROAD may retain REVIEW_PRIORITY, REVIEW, VERIFY and DEPRIORITIZE candidates for layered Human review. FOCUSED retains the higher-priority review set. Neither mode may alter adapters, URLs, queries, locations or source limits.

## Current Career context provider

The public MCP scan uses the private local read-only current Career context provider by default. Request-scoped careerContext is an additive/clarifying overlay only.

Runtime summary exposes:

- career_context_source
- career_context_version

Missing provider state is an execution error; do not reconstruct current exact-role state from chat memory.

## Review packet bridge

Optional downstream review-packet fields:

- role_key
- review_state
  - EXISTING_POOL_CONTINUITY
  - SOURCE_VERIFY_FIRST
  - QUALIFICATION_REVIEW_REQUIRED
  - READY_FOR_JOB_ANALYSIS
- next_step
- job_identity
- source
- job_text
- scan_screening
- qualification_gate
- candidate_context
- preference_context
- company_constraints
- existing_role
- analysis_contract

The bridge is non-semantic: it may expose visible gate markers, but it does not decide final Capability Fit, Qualification, Job Quality or application route. Existing exact roles reuse current Career state.

## Routing

Allowed routes:

- OPPORTUNITY_POOL
- FAST_LANE
- TARGETED_PREPARE
- WATCH
- CLOSE

## Human Review

Required before external action or persistent adoption.
