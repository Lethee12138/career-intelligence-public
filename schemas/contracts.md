# Portable output contracts v0.1

These are required semantic schemas for agent output, not database tables. Markdown reports may use the field labels directly; JSON may use snake_case equivalents. Missing metadata uses literal `UNKNOWN`, not an empty string, inferred default or invented date. `NOT_APPLICABLE` requires rationale. Each substantive statement is a claim object: `{value, kind, source_level, refs, scope, uncertainty}`. Inference must cite premises; UNKNOWN has no positive assertion. References contain `{id, source, location, revision_or_hash, author, observed_at}`. Never treat a reference ID alone as verification.

## Evidence item / match

Evidence item: `id, project_id, source, source_location, ownership_scope, context, action_or_decision, method_or_tool, result_or_output, limitation_or_boundary, metric_scope, confidence_or_uncertainty, public_use_boundary, resume_use_boundary, last_verified_at, provenance, completion_at_cutoff`.

Match row: `requirement_id, requirement_text, requirement_source_location, hierarchy, match_level, evidence_refs, supported_scope, unsupported_scope, gap_types, uncertainty`. Enums are the exact terms in the shared rules. PARTIAL must name the missing part. Each requirement appears exactly once; no hiding weak rows.

## JobAnalysis

- `schema_version`, `candidate_status=HUMAN_REVIEW_REQUIRED`, `job_identity` (company, requisition ID/exact URL, batch, locations), `existing_job_record_ref`, `analysis_date`, `as_of`, `verification_mode`, `evidence_cutoff`, `source_coverage`, `excluded_evidence`.
- Job facts: company, role, recruitment type, location, official source, discovery source, published date, deadline, last/current verification date (UNKNOWN unless verified), status and conflicting observations.
- Qualification: overall ELIGIBLE / VERIFY / NOT ELIGIBLE, scoped gate rows, mandatory/preference distinction, sources and unresolved checks.
- Requirement hierarchy and complete Requirement → Evidence Match rows.
- Actual role interpretation: what it produces, problems owned, title accuracy, premises and inference labels.
- Assessment: all ten named dimensions, each `{judgment, rationale, refs, unknowns}`; no composite score.
- Gaps: typed rows with evidence boundary and decision impact. Risks include work-style, interview, timing/source and company-slot constraints separately.
- Recommendation: allowed category, rationale, decisive positives/negatives, alternatives, what would change it, preparation gate and next action.

## ApplicationBrief

- Exact job/analysis identity and revision, `candidate_status=HUMAN_REVIEW_REQUIRED`, gate `READY_FOR_REVIEW` or `PREPARATION_HOLD` (not authorization).
- Why this role; strongest evidence; likely recruiter concerns; gap/honest response.
- Recommended existing CV Base (name, exact source/version or UNKNOWN); project router (evidence refs, selection reasons, exclusions); portfolio use/permissions or NOT_APPLICABLE with reason.
- Interview evidence stories and follow-up/risk/answer-boundary chains.
- Claim candidates: requirement ID → evidence reference → verified fact reference → bounded proposed text, metric/ownership scope and resume/public-use permission. Broken chains go to gaps.
- Preparation checklist, all remaining VERIFY items, and minimum material questions if justified.
- Optional VibeCodedProjectEvidencePacket: trigger reason, completed project refs, all fields enumerated in claim rules, per-field sources/UNKNOWN, aggregate/event trace distinction, objections and answer boundaries. It never becomes an evidence owner.

Blocked preparation still identifies job, gate reasons and next verification actions, but has no tailored claims, project packet or speculative CV variants. Human approval is not derivable from any report field.

## Core Integration claim/use extension

Apply [stretch policy](../rules/stretch.md). Existing evidence and capability schemas are reused. Add to a claim or match when relevant: `claim_id, use_boundary` (VERIFIED_FACT / DEFENSIBLE_STRETCH / SPECULATIVE_UNSUPPORTED), `verification_scope`, `source_capability_refs`, `evidence_refs`, `bridge_reasoning`, `unproven_scope`, `allowed_use`, `prohibited_overclaim`, `defensibility` (L1 What / L2 Transfer / L3 Boundary with refs and review disposition). Preserve the original `kind`, source level, scope, permissions and epistemic status. DEFENSIBLE_STRETCH match_level is PARTIAL, not SUPPORTED.

For explicitly requested historical integration review, ApplicationBrief may contain `framing_review` with purpose=HISTORICAL_INTEGRATION_REVIEW, disposition=NOT_FOR_ADOPTION, weak/strong wording comparisons, source/bridge chain and internal L1–L3. It remains separate from `claim_candidates`, which stays empty under PREPARATION_HOLD. No packet or new CV is implied. Without that explicit request, the existing default HOLD behavior applies.

Integration artifact references each stage's output ID/revision and input IDs, preserving exact job identity from analysis into preparation. Trace final strategy/framing → match/assessment → role hypothesis → capability → source evidence. Broken links are named, not filled by semantic similarity. Market observation history can contradict a job-specific hypothesis without deleting its capability premises.

## Job Quality & Offer Preference extension v0.1.1

Reuse the existing claim/reference model and [Job Quality rule](../rules/job-quality.md); no second candidate, offer or assessment owner. Preference reference: `profile_id, version, confirmed_at, author/provenance, source_ref, topic, strength` (HARD_FLOOR / STRONG_NEGATIVE / STRONG_PREFERENCE / POSITIVE_BONUS / TRADEABLE / UNKNOWN), `stance, rationale, scope, calibration_status`. A personal reference is not a market observation. HARD_FLOOR needs explicit Human source and context; no universal numeric salary floor is inferred.

Add optional `job_quality` to JobAnalysis and carry it by reference into ApplicationBrief: `profile_ref, observation_refs, as_of, context` (city, role_family, recruitment_year, company_type, living_cost_basis), `items`, `job_quality_fit` (HIGH / MIXED / LOW / UNKNOWN), `performance_environment_risks`, `tradeoffs`, `recommendation_effect`, `verify_items`. Each item uses existing `{value, kind, source_level, refs, scope, uncertainty}` plus `preference_ref, strength, judgment, decision_impact`. Topics: Compensation, Total Compensation, Workload/Rest, Annual Leave, Team/Manager Environment, Stability/Risk, Growth/Ownership, Career Capital, Work Interest, Commute/Work Arrangement, Travel, Probation. These are detailed observations, not twelve new scores; original ten dimensions remain unchanged.

Total Compensation breakdown: base salary, guaranteed pay/months, bonus/year-end and guarantee status, housing subsidy, talent subsidy, meal/transport, social insurance, housing fund and other material benefits. Preserve currency, period, gross/net basis, guarantee, eligibility, realistic obtainability, timing and sources. Effective Compensation describes dependable cash/obtainable benefits and material costs without an invented net figure. Unknown benefit is not zero, advertised bonus is not guaranteed cash. Calibration: subjective_reference vs personal_floor vs MARKET_VERIFY/current_market_evidence, keyed to City × Role Family × Graduate Market/year/company type.

Tradeoff: `cost, duration, specific_return, return_evidence_refs, mitigation, review_or_exit_condition, Human_decision`; no automatic weighted score. Offer Quality can later group the same items into Compensation, Lifestyle, Psychological Sustainability/Performance Environment, Career Capital, Stability and Work Interest, without a new workflow. Ordinary UNKNOWN quality fields do not automatically become critical preparation blockers. Existing source/qualification gates and Human Review stay intact.

## Global Market & Eligibility extension v0.1.2

Apply [global-market rule](../rules/global-market.md). Add `market_context` with independent `employment_market`, `company_type/nationality`, `work_location` (country/region/city), `market_preference_ref`, `temporary_execution_priority`, and ambiguity notes. Use existing sourced claim objects; corporate nationality does not fill employment jurisdiction.

Add `work_right` with `candidate_authorization` (current status, scope, restrictions, expiry, refs), `sponsorship_need`, `employer_sponsorship` (offers / may / does_not / unknown, exact role/program applicability, refs), `other_routes`, `resolution_state` (ALREADY_AUTHORISED / SPONSORSHIP_REQUIRED / SPONSORSHIP_AVAILABLE / SPONSORSHIP_VERIFY / SPONSORSHIP_UNAVAILABLE / OTHER_ROUTE_VERIFY), `route_conditions`, `verification_as_of`, `uncertainties`, and, when relevant, separate `current_residence`, `required_work_territory`, `residence_requirement`, `overseas_remote_allowed`, `relocation_before_start`, `work_right_at_required_location_and_start_date`, `territory_gate`, `territory_status`, `territory_risks` and `territory_readiness`. Keep separate qualification rows and overall ELIGIBLE / VERIFY / NOT ELIGIBLE. No summary string replaces the source facts or why a gate passed/failed. Current work right never supplies residence or work-territory eligibility; Remote/Home Based never supplies GLOBAL_REMOTE without authority.

Optional `market_benchmark` uses the existing claim/reference contract: benchmark_id, market/country, region/city, role_family, career_stage/graduate_status, recruitment_year, currency, salary_basis (period, gross/net, guaranteed/variable), salary_range or UNKNOWN, total_compensation_notes, cost_of_living_context, typical_benefits_if_supported, work_authorization_context, sponsorship_context, sourceRefs, captured_at, verified_at or UNKNOWN, evidence_level, limitations. It is external market evidence, not personal preference, individual employer terms or candidate authorization. No global benchmark dataset is prefilled.

Cross-market comparison context: periods, taxes where relevant, living/rent costs, benefits, hours, pension/social insurance, relocation and visa costs/constraints, each sourced or UNKNOWN with applicability rationale. Conversion alone cannot determine a winner. Position/Discovery can reference this context without it altering capability statuses. ApplicationBrief may carry strategy_scope=STRATEGY_ONLY while sponsorship/work-right VERIFY and PREPARATION_HOLD remain explicit; no full materials until existing gates pass.

## Dated Calibration extension v0.1.3

Optional market_benchmark reference imports follow [calibration rules](../rules/market-calibration.md). Preserve salary CSV fields verbatim including route, all four bands, currency_basis, confidence, captured_date, important_limitations, traceability_status, source_refs/types/capture_dates, sample_count/scope, salary_transparent_postings, derivation_type/note and separate visa_salary_gate/visa_source_refs. Reference identity = file + row + import SHA-256. Add last_verified (nullable), category, recheck state and reviewer as_of/captured_date/decision/reason; never infer last_verified from capture. Comparison records actual role base/source separately, market_quality_band, visible provenance and freshness; no automatic_action or percentile. Benefits context uses separate market cells, original volatility and missing-metadata markers. Volatile legal/policy values are historical only until fresh authority verification. This extends the existing optional market_benchmark rather than creating candidate evidence or a new workflow.

## Job Search Execution v0.2

Use [execution contracts](search-execution.md) for SearchExecutionHandoff, JobCandidateBatch, JobCandidate and Application Pool proposals. Intake/route does not replace JobAnalysis/ApplicationBrief, qualification, evidence-use permissions or application status.
