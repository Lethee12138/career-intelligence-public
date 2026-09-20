# Job Quality integration v0.1.1

Reuse [assessment](opportunity-assessment.md), [evidence](evidence.md), [source rules](source-and-inference.md), [questioning](user-questioning.md), [stretch](stretch.md) and [contracts](../schemas/contracts.md). Caller-supplied preferences may be illustrated by the [public synthetic preference example](../references/job-quality-profile.example.md). Capability Fit and Job Quality Fit answer different questions; neither rewrites the other's evidence.

Preference strength: HARD_FLOOR (rare, explicit/contextual), STRONG_NEGATIVE, STRONG_PREFERENCE, POSITIVE_BONUS, TRADEABLE, UNKNOWN. ACCEPTABLE is a descriptive stance, not a seventh strength: use TRADEABLE or a neutral permitted condition with rationale. STRONG_CONCERN maps to STRONG_NEGATIVE; PERFORMANCE_ENVIRONMENT_RISK is a distinct risk annotation, not a strength or skill rating. Housing fund LOW priority is qualitative, never a numeric weight.

Inspect existing profile before asking. Each employer/offer observation needs its own source, date, scope, kind and uncertainty; profile confirmation does not verify an offer. Distinguish an official promise from actual team practice and usable leave. Brand, size, industry and title cannot supply salary/culture facts. Rumors retain anecdotal confidence and motivate verification; do not silently treat them as confirmed chronic conditions. No automatic search, survey or negotiation. Salary calibration is MARKET_VERIFY until actual contextual market evidence is supplied or separately requested; this increment's comparisons are synthetic only.

## Assessment and recommendation

Add `job_quality` detail beside the original ten dimensions, not as new weighted dimensions. Cover compensation, total compensation, workload/rest, annual leave, team/manager, stability/risk, growth/ownership, career capital, work interest, commute/arrangement, travel and probation as evidence permits. Missing fields are UNKNOWN, not zero or positive. Map pay/cost/commute/benefits to Practical Fit; work/rest/leave to Work-style Preference Fit; management to PERFORMANCE_ENVIRONMENT_RISK and its work-style implications; ownership/mobility to Career Value; work interest to Interest / Preference Fit. Reference shared observations once, avoiding duplicated independent scores. No weighted total or “benefit points.”

A known structural 996/high-pressure environment, materially inadequate contextual pay, serious probation/elimination or payroll risk must materially lower the recommendation even with high Capability Fit. Preserve the capability assessment and explain the job-quality reason. Typically move an otherwise active recommendation to Low Priority pending Human trade-off; an explicit HARD_FLOOR breach normally means Not Viable Currently in that scope. Do not promote an existing closed/ineligible or unresolved qualification/source result because job quality is appealing.

Compensation is a material constraint; a pleasant team does not cure pay below a grounded living floor. Conversely, when both options afford a reasonable standard, a salary premium alone cannot erase structural pressure, poor rest or harmful management. Benefits/hybrid/brand are supporting positives, never automatic offsets. Compare stable guaranteed amounts separately from contingent bonuses; subsidies require realistic obtainability and avoid double counting. No universal 5k/6k/8k/9k cutoff or salary cap; no hardcoded 30% trade threshold.

Startup is not a rejection reason. Evaluate actual payroll/viability/organization observations, not size. A moderate-risk opportunity with concrete compensation, interest, ownership and mobility can be worth more than stable low-value work. A bounded-hardship exception must name cost, duration, credible return, support/mitigation and review/exit conditions. An unbounded or vague “suffer now” argument cannot restore priority. Even a defensible exception remains for Human decision, not automatic restoration or approval.

Annual leave is materially differentiating when actually usable (e.g. 5 vs 10–15); nominal leave without access is a concern. Identify structural versus exceptional overtime using frequency, duration and compensation/rest. Keep management risk visible before further preparation effort; it concerns the candidate's performance environment as well as personal dislike, without claiming a quantified or diagnosed effect. Probation percentage alone does not imply a red flag; length plus meaningful risk/unclear criteria changes the judgment. Legal compliance, actual elimination rates and subsidy eligibility cannot be guessed.

## Workflow behavior

/position keeps an environment/lifestyle/first-job-value context alongside capability positioning. Do not downgrade inferred or demonstrated capability because the candidate avoids high pressure.

/discover retains capability-adjacent but preference-poor roles with lower pursuit priority and explicit reasons. Flag pay/team/work-family risks only when supported, and record MARKET_VERIFY needs without inventing openings or culture.

/analyse-job is the main integration point: populate available job_quality detail, show Capability Fit separately from Job Quality Fit, and explain the resulting recommendation change or trade-off. Do not require every quality field to be known. A hard employer eligibility rule remains separate from a personal floor.

/prepare-application carries known strong concerns and the prior recommendation into the brief before additional effort. Unknown routine Job Quality fields alone do not block preparation and must not be copied automatically into critical_unknowns. Existing identity, qualification, source and claim-use gates remain in force. A known severe signal may legitimately lower priority and therefore restrict high-investment tailoring; this is a deliberate decision, not missing-field validation. Keep next questions limited to decision-changing quality uncertainties. No offer negotiation or new /compare-offers workflow.

The shared block can later support Offer Quality Assessment grouped as Compensation, Lifestyle, Psychological Sustainability/Performance Environment, Career Capital, Stability and Work Interest. It is a foundation for explainable comparison, not an automatic selection engine.

Global scope v0.1.2: [global-market rules](global-market.md) retain stable personal preferences while calibrating pay and benefit conventions by employment market. The existing RMB/China references are scoped examples, not worldwide benchmarks.
