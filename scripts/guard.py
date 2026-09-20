"""Read-only, standard-library guards for explicitly grounded Career inputs.

These functions do not read owners, browse, infer semantic matches, generate CVs,
rank jobs or verify that a caller's assertions are true. Agents must do that
grounding under SKILL.md. Unknown or malformed decisive data fails closed.
"""
from datetime import date

UNKNOWN = "UNKNOWN"
HIERARCHY = {"MUST", "STRONG PREFERENCE", "NICE TO HAVE", "UNKNOWN / AMBIGUOUS"}
MATCH = {"SUPPORTED", "PARTIAL", "UNSUPPORTED", UNKNOWN}
DIMENSIONS = (
    "Capability Fit", "Evidence Fit", "Experience Fit", "Eligibility Fit",
    "Practical Fit", "Career Value", "Interest / Preference Fit",
    "Work-style Preference Fit", "Interview Process Risk", "Stretch Level",
)
RECOMMENDATIONS = {
    "High Priority Apply", "Apply", "Strategic Stretch", "Explore", "Watch",
    "Low Priority", "Not Viable Currently",
}
EVIDENCE_FIELDS = (
    "source", "source_location", "ownership_scope", "context", "action_or_decision",
    "method_or_tool", "result_or_output", "limitation_or_boundary", "metric_scope",
    "confidence_or_uncertainty", "public_use_boundary", "resume_use_boundary",
    "last_verified_at",
)
PACKET_FIELDS = (
    "user_problem", "why_selected", "end_to_end_flow", "product_decisions",
    "technical_decisions", "ai_contribution", "human_contribution", "team_contribution",
    "testing_evaluation", "discovered_problems", "iteration", "real_feedback",
    "approved_artifact_refs", "interviewer_objections", "answer_boundaries",
)
SALES = {"sales_quota", "acquisition_kpi", "revenue_ownership",
         "persuasive_selling", "negotiation_heavy_client_work"}
INTERVIEW = {"group_assessment", "case_interview", "impromptu_presentation"}


def known(value):
    return value is not None and value != "" and value != UNKNOWN


def normalized_evidence(item):
    """Non-mutating projection; missing metadata never becomes a default fact."""
    return {**item, **{k: item.get(k) if known(item.get(k)) else UNKNOWN
                      for k in EVIDENCE_FIELDS}}


def iso(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def window_match(candidate_start, candidate_end, required_start, required_end):
    dates = [iso(v) for v in (candidate_start, candidate_end, required_start, required_end)]
    if None in dates:
        return "VERIFY"
    a, b, c, d = dates
    if a > b or c > d:
        return "VERIFY"
    if b < c or a > d:
        return "NOT ELIGIBLE"
    return "ELIGIBLE" if c <= a <= b <= d else "VERIFY"


def qualification(checks, coverage_complete=False):
    """Only explicit MUST failures exclude; preferences cannot become hard gates."""
    uncertain = not coverage_complete or not checks
    failed = False
    for check in checks:
        hierarchy = check.get("hierarchy")
        if hierarchy not in HIERARCHY or hierarchy == "UNKNOWN / AMBIGUOUS":
            uncertain = True
        elif hierarchy == "MUST":
            if not check.get("refs") or check.get("verified") is not True:
                uncertain = True
            elif check.get("result") == "FAIL":
                failed = True
            elif check.get("result") != "PASS":
                uncertain = True
    return "NOT ELIGIBLE" if failed else "VERIFY" if uncertain else "ELIGIBLE"


def resolve_status(role_key, observations, as_of, mode="HISTORICAL_SNAPSHOT"):
    """Exact identity + inspected authority, ordered by observation, not mirror date.

    All snapshots are immutable inputs. LIVE additionally requires a same-day
    check; historical reports never gain live preparation authority.
    """
    day = iso(as_of)
    if not known(role_key) or day is None:
        return {"role_key": role_key, "status": "VERIFY", "live_verified": False, "refs": []}
    authorities = [o for o in observations
                   if o.get("role_key") == role_key
                   and o.get("authority_for_role") is True
                   and o.get("inspected_original") is True
                   and o.get("ref") and iso(o.get("observed_at")) is not None
                   and iso(o["observed_at"]) <= day]
    if not authorities:
        return {"role_key": role_key, "status": "VERIFY", "live_verified": False, "refs": []}
    latest = max(o["observed_at"] for o in authorities)
    current = [o for o in authorities if o["observed_at"] == latest]
    states = {"CLOSED" if o.get("status") == "FILLED" else o.get("status") for o in current}
    status = next(iter(states)) if len(states) == 1 else "VERIFY"
    if status not in {"OPEN", "CLOSED"}:
        status = "VERIFY"
    return {"role_key": role_key, "status": status, "live_verified": mode == "LIVE" and latest == as_of
            and status != "VERIFY", "refs": [o["ref"] for o in current]}


def match_errors(row, evidence, excluded=(), completed_only=False):
    errors = []
    level = row.get("match_level")
    if level not in MATCH:
        errors.append("invalid match level")
    if row.get("hierarchy") not in HIERARCHY:
        errors.append("invalid requirement hierarchy")
    if level in {"SUPPORTED", "PARTIAL"}:
        refs = row.get("evidence_refs", [])
        if not refs:
            errors.append("positive match needs evidence")
        for ref in refs:
            item = evidence.get(ref, {})
            if not item or not known(item.get("source_location")) or item.get("inspected") is not True:
                errors.append("unresolved or uninspected evidence: " + ref)
            if item.get("project_id") in excluded or ref in excluded:
                errors.append("excluded evidence: " + ref)
            if completed_only and item.get("completion_at_cutoff") != "COMPLETED":
                errors.append("evidence not completed at cutoff: " + ref)
        if not known(row.get("supported_scope")):
            errors.append("positive match needs bounded scope")
    if level == "PARTIAL" and not known(row.get("unsupported_scope")):
        errors.append("partial match must expose gap")
    return errors


def preparation_gate(analysis):
    reasons = []
    if not known(analysis.get("role_key")):
        reasons.append("job identity VERIFY")
    status = analysis.get("source_status", {})
    if status.get("role_key") != analysis.get("role_key") or not status.get("refs"):
        reasons.append("authority observation not bound to this job")
    if status.get("status") != "OPEN":
        reasons.append("authority status not OPEN")
    if status.get("live_verified") is not True:
        reasons.append("current authority revalidation required")
    if analysis.get("qualification") != "ELIGIBLE":
        reasons.append("hard qualification unresolved or failed")
    territory = analysis.get("work_territory")
    if not isinstance(territory, dict):
        territory = analysis.get("work_right", {})
    if isinstance(territory, dict) and territory.get("territory_material"):
        territory_gate = territory.get("territory_gate", "VERIFY")
        human_accepts = analysis.get("human_accepts_territory_uncertainty") is True
        if territory_gate == "NOT ELIGIBLE":
            reasons.append("required work territory/residence is not viable currently")
        elif territory_gate != "ELIGIBLE" and not human_accepts:
            reasons.append("work territory/residence feasibility VERIFY")
    if analysis.get("evidence_justifies_preparation") is not True:
        reasons.append("evidence does not justify preparation")
    if analysis.get("recommendation") not in {"High Priority Apply", "Apply", "Strategic Stretch"}:
        reasons.append("recommendation does not justify active tailoring")
    if not isinstance(analysis.get("critical_unknowns"), list) or analysis["critical_unknowns"]:
        reasons.append("critical unknowns remain")
    if type(analysis.get("one_active_application")) is not bool:
        reasons.append("company application constraints VERIFY")
    if analysis.get("one_active_application") is True:
        slot = analysis.get("company_slot", UNKNOWN)
        if slot not in {"CLEAR", analysis.get("role_key")}:
            reasons.append("company slot occupied or VERIFY")
    return {"gate": "PREPARATION_HOLD" if reasons else "READY_FOR_REVIEW", "reasons": reasons}


def work_style(duties, assessments):
    negative = [d["signal"] for d in duties if d.get("core_daily") is True
                and d.get("signal") in SALES]
    interview = [a for a in assessments if a in INTERVIEW]
    return {"work_style": "LOW" if negative else "UNKNOWN" if not duties else "NO_NEGATIVE_SIGNAL",
            "negative_signals": negative, "interview_risks": interview}


def claim_errors(claim, requirements, evidence, verified_facts, public=False):
    errors = []
    rid, eid, fid = (claim.get(k) for k in ("requirement_id", "evidence_id", "fact_id"))
    fact, item = verified_facts.get(fid, {}), evidence.get(eid, {})
    if rid not in requirements or eid not in evidence or fid not in verified_facts:
        errors.append("broken requirement/evidence/fact chain")
    if fact.get("evidence_id") != eid or fact.get("verified") is not True or not fact.get("source_location"):
        errors.append("fact not verified against this evidence")
    if item.get("resume_use_boundary") != "ALLOWED":
        errors.append("resume use requires review")
    if public and item.get("public_use_boundary") != "ALLOWED":
        errors.append("public use requires review")
    if not known(claim.get("text")) or claim.get("scope_reviewed") is not True:
        errors.append("claim wording/scope needs semantic Human Review")
    # Scope review is an explicit input assertion, never inferred from text.
    if not set(claim.get("asserted_capabilities", [])).issubset(set(fact.get("supported_capabilities", []))):
        errors.append("claim capabilities exceed verified fact")
    return errors


def packet_errors(packet, evidence):
    errors = []
    if packet.get("trigger") not in {"AI_ASSISTED_BUILD", "PROTOTYPE_OWNERSHIP",
                                     "HUMAN_AI_JUDGEMENT", "PRODUCT_TECHNICAL_BOUNDARY"}:
        errors.append("packet requires target-specific trigger")
    if packet.get("truth_source") is not False:
        errors.append("packet cannot be a truth source")
    for field in PACKET_FIELDS:
        entry = packet.get(field)
        if not isinstance(entry, dict) or not known(entry.get("value")):
            if not isinstance(entry, dict) or entry.get("value") != UNKNOWN:
                errors.append("missing packet field: " + field)
            continue
        if entry.get("kind") not in {"FACT", "EXTERNAL_REPORT", "INFERENCE"}:
            errors.append("packet field lacks epistemic kind: " + field)
        refs = entry.get("refs", [])
        if not refs:
            errors.append("packet field lacks evidence/premises: " + field)
        for ref in refs:
            item = evidence.get(ref, {})
            if item.get("completion_at_cutoff") != "COMPLETED" or item.get("inspected") is not True:
                errors.append("packet requires inspected completed evidence: " + ref)
    if packet.get("event_trace_status") != "VERIFIED" and packet.get("change_events"):
        errors.append("cannot invent individual change events")
    return errors


def assessment_errors(assessment):
    errors = []
    if set(assessment.get("dimensions", {})) != set(DIMENSIONS):
        errors.append("all ten independent dimensions required")
    for name, value in assessment.get("dimensions", {}).items():
        if not isinstance(value, dict) or not known(value.get("rationale")):
            errors.append("dimension requires explanation: " + name)
    if assessment.get("recommendation") not in RECOMMENDATIONS:
        errors.append("unknown recommendation")
    if any(k in assessment for k in ("match_percentage", "match_score", "total_score")):
        errors.append("no aggregate match score")
    if assessment.get("mandatory_domain_gap") is True and assessment.get("recommendation") == "High Priority Apply":
        errors.append("city/title cannot override domain evidence gate")
    return errors
