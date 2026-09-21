# Role Hypothesis / Discovery Report

Reuse [claims and references](contracts.md), [capability profile](capability-profile.md), the [capability → role-family → market-title taxonomy](capability-role-family-taxonomy.md) and [discovery rules](../rules/discovery.md). This is a semantic output contract, not a job tracker.

Envelope: schema_version, HUMAN_REVIEW_REQUIRED, as_of, mode (ANALYSIS_ONLY / MARKET_VALIDATED), source_coverage, profile_ref, industry_scope, exclusions with sourced reasons, questioning_stop_reason, `ai_neutral_by_default=true`, capability_roots_considered, coverage_audit and discovery_stop_reason. Coverage state is COVERAGE_UNREVIEWED / COVERAGE_BIAS_DETECTED / COVERAGE_SUFFICIENT; sufficient requires reviewed relevant-root coverage, not merely several strong roles.

Each hypothesis: id; role_or_family; optional taxonomy_ref; why_generated; discovery_routes (A / B / C / D); capability_root_refs; cross_domain_axes; AI involvement (NONE / AI-ENABLED / AI-CORE / AGENT-CORE); actual_work_and_outputs; strongest_candidate_evidence; counterevidence; likely_hard_gaps; preference_risks; title_variants; multiple company/team types; market_validation_state (UNVALIDATED / MARKET_SIGNAL_FOUND / VALIDATED_BY_CURRENT_JD / CONTRADICTED / DEFERRED); scope; uncertainty; validation_history (original hypothesis retained plus dated observations and refs). Media/communication crossings remain ordinary cross-domain hypotheses, not a separate lane.

Route bridge: A includes seed reason, support, counter, adjacent and contradiction sought; B includes capability ID/status → work problem → team → role; C includes INFERRED capability ID, traceable behavior and ownership → plausible use → role; D includes repeated problem refs → owning teams → responsibilities → search terms. A hypothesis can cite multiple routes, each with its bridge. POTENTIAL is a verification queue, not Route C evidence.

Search strategy for EACH hypothesis: core titles, adjacent titles, responsibility terms, problem terms, output terms, negative terms/title traps, company/team categories. These are search suggestions, not searches performed or evidence of fit.

Validation plan: what actual duties would confirm/weaken; hard requirements to inspect; missing candidate evidence; relevant preference checks. Observation: exact job/version, source ref, kind/source level, date/as_of, inspected-original/current status, actual duties, title variants, mandatory vs preferred requirements, confirm/weaken/contradict rationale and scope. Keep historical vs current explicit. A family can remain plausible while an exact opening is contradicted.

Recommendation disposition: hypothesis only until market evidence exists; any job recommendation requires /analyse-job with the existing ten dimensions and qualification gate. Do not duplicate that assessment here or turn market corroboration into application readiness.
