"""Single user-facing entrypoint for bounded Career Intelligence job scanning.

One invocation runs public-source scanning, deduplication/triage and the
Career review bridge. It produces review artifacts only. No application,
canonical mutation, login, upload, recruiter contact or material editing.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.career_context_provider import load_current_career_context
    from scripts.job_scan_batch import run_batch
    from scripts.job_scan_review_bridge import build_review_packets
    from scripts import job_source_runtime as source_runtime
except ModuleNotFoundError:  # direct execution from repository root
    from career_context_provider import load_current_career_context
    from job_scan_batch import run_batch
    from job_scan_review_bridge import build_review_packets
    import job_source_runtime as source_runtime


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_PRESET = ROOT / "config/current-job-scan-preset.json"
DEFAULT_MARKET_DISCOVERY_PROFILE = ROOT / "references/market-discovery-profile.default.json"


POOL_RETAIN_STATES = {
    "BROAD": ("REVIEW_PRIORITY", "REVIEW", "VERIFY", "DEPRIORITIZE"),
    "FOCUSED": ("REVIEW_PRIORITY", "REVIEW"),
}
SCAN_MODES = {"configured_review", "market_discovery", "hybrid_discovery"}


def _source_scope(config: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for source in config.get("sources") or []:
        rows.append(
            {
                "adapter": source.get("adapter"),
                "mode": source.get("mode", "discover"),
                "url": source.get("url"),
                "urls": source.get("urls"),
                "query": source.get("query"),
                "location": source.get("location"),
                "limit": source.get("limit"),
                "verify_limit": source.get("verify_limit"),
            }
        )
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib
    return {
        "immutable_for_pool_mode": True,
        "sources": rows,
        "fingerprint": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def _pool_view(scan: dict[str, Any], pool_mode: str) -> dict[str, Any]:
    mode = str(pool_mode or "BROAD").upper()
    if mode not in POOL_RETAIN_STATES:
        raise ValueError("poolMode must be BROAD or FOCUSED")
    retain = set(POOL_RETAIN_STATES[mode])
    rows = [
        candidate
        for candidate in scan.get("candidate_pool") or []
        if (candidate.get("screening") or {}).get("state") in retain
    ]
    return {
        "mode": mode,
        "retained_states": list(POOL_RETAIN_STATES[mode]),
        "retained_candidate_count": len(rows),
        "candidate_keys": [
            candidate.get("dedupe_identity")
            or f"{candidate.get('company')}:{candidate.get('external_job_id')}"
            for candidate in rows
        ],
        "candidates": [
            {
                "company": candidate.get("company"),
                "external_job_id": candidate.get("external_job_id"),
                "role": candidate.get("role"),
                "location": candidate.get("location"),
                "verification_status": candidate.get("verification_status"),
                "screening_state": (candidate.get("screening") or {}).get("state"),
                "screening_reasons": (candidate.get("screening") or {}).get("reasons"),
                "source_url": candidate.get("source_url"),
                "exact_role": candidate.get("role"),
                "official_source": candidate.get("official_source", "UNKNOWN"),
                "live_status": candidate.get(
                    "live_status", candidate.get("verification_status", "UNKNOWN")
                ),
                "qualification_facts": candidate.get("qualification_facts", []),
                "deadline": candidate.get("deadline", "UNKNOWN"),
                "application_rule": candidate.get("application_rule", "UNKNOWN"),
                "provenance": candidate.get("provenance", []),
                "uncertainty": candidate.get("uncertainty", []),
                "role_family": candidate.get("role_family", "UNKNOWN"),
                "company_coverage_bucket": candidate.get(
                    "company_coverage_bucket", "UNKNOWN"
                ),
                "ai_involvement": candidate.get("ai_involvement", "UNKNOWN"),
                "why_matched": candidate.get("why_matched", "UNKNOWN"),
                "evidence_refs": candidate.get("evidence_refs", []),
                "risk": candidate.get("risk", candidate.get("risks", [])),
                "next_action": candidate.get("next_action") or {
                    "REVIEW_PRIORITY": "REVIEW_ROLE",
                    "REVIEW": "REVIEW_ROLE",
                    "VERIFY": "VERIFY_OFFICIAL_SOURCE",
                    "DEPRIORITIZE": "REVIEW_PREFERENCE_RISK",
                    "CLOSE": "SKIP_CLOSED",
                }.get((candidate.get("screening") or {}).get("state"), "REVIEW_ROLE"),
            }
            for candidate in rows
        ],
        "source_scope_changed": False,
    }


def _empty_scan(scan_id: str, captured_at: str) -> dict[str, Any]:
    return {
        "scan_id": scan_id,
        "captured_at": captured_at,
        "source_results": [],
        "raw_record_count": 0,
        "deduped_count": 0,
        "screening_counts": {},
        "candidate_pool": [],
        "boundary": {
            "read_only_public_sources": True,
            "login": False,
            "application": False,
            "upload": False,
            "external_contact": False,
            "persistent_career_adoption": False,
            "final_fit_decision": False,
        },
    }


def _normalize_discovery(discovery: dict[str, Any] | None) -> dict[str, Any]:
    raw = discovery if isinstance(discovery, dict) else {}
    return {
        "capability_profile": raw.get("capability_profile", raw.get("capabilityProfile")),
        "role_hypotheses": raw.get("role_hypotheses", raw.get("roleHypotheses", [])),
        "location_scope": raw.get("location_scope", raw.get("locationScope", [])),
        "company_types": raw.get("company_types", raw.get("companyTypes", [])),
        "candidate_constraints": raw.get("candidate_constraints", raw.get("candidateConstraints", {})),
        "market_scope": raw.get("market_scope", raw.get("marketScope", [])),
        "input_refs": raw.get("input_refs", raw.get("inputRefs", [])),
        "candidates": raw.get("candidates", raw.get("discovery_candidates", [])),
        "taxonomy_ref": raw.get("taxonomy_ref", raw.get("taxonomyRef")),
        "provider": raw.get("provider", "EXTERNAL_WEB_DISCOVERY_HANDOFF"),
        "provider_run": raw.get("provider_run", raw.get("providerRun", {})),
    }


def _market_discovery_profile(career_context: dict[str, Any]) -> dict[str, Any]:
    """Load public neutral defaults, then apply caller-scoped profile values."""
    base = _load_json(DEFAULT_MARKET_DISCOVERY_PROFILE)
    overlay = career_context.get("market_discovery_profile")
    if isinstance(overlay, dict):
        merged = copy.deepcopy(base)
        for key, value in overlay.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **copy.deepcopy(value)}
            else:
                merged[key] = copy.deepcopy(value)
        return merged
    return base


def _coverage_bucket(candidate: dict[str, Any]) -> str:
    return str(
        candidate.get("company_coverage_bucket")
        or candidate.get("companyCoverageBucket")
        or candidate.get("company_type")
        or candidate.get("companyType")
        or "UNKNOWN"
    ).strip().upper()


def _audit_market_discovery_coverage(
    candidates: list[dict[str, Any]],
    profile: dict[str, Any],
    provider_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safeguard = profile.get("coverage_safeguard") or {}
    min_known = int(safeguard.get("min_known_candidates", 3))
    threshold = float(safeguard.get("head_bucket_share_threshold", 0.6))
    head_buckets = {str(v).upper() for v in safeguard.get("head_company_buckets", [])}
    supplement_buckets = [str(v).upper() for v in safeguard.get("supplement_buckets", [])]
    allowed_buckets = {
        str(v).upper() for v in profile.get("company_coverage_buckets", [])
    }
    buckets = [_coverage_bucket(candidate) for candidate in candidates]
    known = [bucket for bucket in buckets if bucket in allowed_buckets]
    distribution: dict[str, int] = {}
    for bucket in known:
        distribution[bucket] = distribution.get(bucket, 0) + 1
    head_count = sum(distribution.get(bucket, 0) for bucket in head_buckets)
    head_share = (head_count / len(known)) if known else None
    missing = [bucket for bucket in supplement_buckets if distribution.get(bucket, 0) == 0]
    provider_run = provider_run if isinstance(provider_run, dict) else {}
    coverage_evidence = provider_run.get("coverage_evidence")
    coverage_evidence = coverage_evidence if isinstance(coverage_evidence, dict) else {}
    evidence_refs = coverage_evidence.get("refs")
    evidence_refs = evidence_refs if isinstance(evidence_refs, list) else []
    concentration_supported = bool(
        coverage_evidence.get("head_concentration_supported") is True
        and evidence_refs
    )
    supplement_count = provider_run.get("coverage_supplement_count")
    supplement_pass = bool(
        provider_run.get("coverage_supplement_pass") is True
        or (
            isinstance(supplement_count, (int, float))
            and not isinstance(supplement_count, bool)
            and supplement_count > 0
        )
    )
    imbalance = bool(
        len(known) >= min_known
        and head_share is not None
        and head_share > threshold
        and missing
        and not concentration_supported
        and not supplement_pass
    )
    state = (
        str(safeguard.get("imbalance_state") or "DISCOVERY_COVERAGE_IMBALANCE")
        if imbalance
        else "COVERAGE_REVIEWED"
        if len(known) >= min_known
        else "COVERAGE_UNREVIEWED"
    )
    return {
        "state": state,
        "profile_id": profile.get("profile_id", "UNKNOWN"),
        "known_candidate_count": len(known),
        "unknown_or_unmapped_candidate_count": len(candidates) - len(known),
        "total_candidate_count": len(candidates),
        "company_coverage_distribution": distribution,
        "head_bucket_share": head_share,
        "market_evidence_supports_concentration": concentration_supported,
        "market_evidence_refs": evidence_refs,
        "supplement_pass_already_completed": supplement_pass,
        "missing_supplement_buckets": missing,
        "supplement_required": imbalance,
        "supplement_buckets": missing if imbalance else [],
        "automatic_supplement": bool(safeguard.get("automatic_supplement", False)),
        "interpretation": "Discovery-result coverage heuristic only; not a market-distribution claim.",
    }


def _make_discovery_handoff(
    discovery: dict[str, Any],
    scan_id: str,
    created_at: str,
    market_profile: dict[str, Any],
) -> dict[str, Any]:
    """Reuse the accepted Search Execution contract without generating facts."""
    import sys

    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from search_execution import make_handoff

    role_hypotheses = discovery.get("role_hypotheses")
    if not isinstance(role_hypotheses, list) or not role_hypotheses:
        raise ValueError("market_discovery requires discovery.roleHypotheses")
    constraints = discovery.get("candidate_constraints") or []
    human_constraints = constraints if isinstance(constraints, list) and all(
        isinstance(item, str) for item in constraints
    ) else []
    human_constraints = human_constraints + [
        f"Market discovery default profile: {market_profile.get('profile_id', 'UNKNOWN')}",
        "Company size, big-tech status, familiar brand and configured adapter presence do not receive discovery priority bonuses.",
        "company adapter != market scope",
    ]
    human_constraints.extend(
        f"Strong negative work-style signal: {item}"
        for item in market_profile.get("work_style_negative_signals", [])
    )
    taxonomy_path = Path(__file__).resolve().parents[1] / "schemas/capability-role-family-taxonomy.md"
    workflow_path = Path(__file__).resolve().parents[1] / "workflows/discover.md"
    if not taxonomy_path.exists() or not workflow_path.exists():
        raise ValueError("discovery taxonomy/workflow resources unavailable")
    payload = {
        "role_hypotheses": role_hypotheses,
        "location_scope": discovery.get("location_scope") or None,
        "input_refs": discovery.get("input_refs") or [],
        "human_constraints": human_constraints,
        "coverage_plan": {
            "market_scope": discovery.get("market_scope") or [],
            "company_types": discovery.get("company_types") or [],
            "default_profile_id": market_profile.get("profile_id", "UNKNOWN"),
            "company_priority": copy.deepcopy(market_profile.get("company_priority") or {}),
            "company_coverage_buckets": copy.deepcopy(
                market_profile.get("company_coverage_buckets") or []
            ),
            "decision_priority": copy.deepcopy(market_profile.get("decision_priority") or []),
            "market_location_preferences": copy.deepcopy(
                market_profile.get("market_location_preferences") or {}
            ),
            "location_ordering": copy.deepcopy(
                market_profile.get("location_ordering") or []
            ),
            "coverage_safeguard": copy.deepcopy(
                market_profile.get("coverage_safeguard") or {}
            ),
            "taxonomy_ref": discovery.get("taxonomy_ref") or "schemas/capability-role-family-taxonomy.md",
            "taxonomy_sha256": hashlib.sha256(taxonomy_path.read_bytes()).hexdigest(),
            "discovery_workflow_ref": "workflows/discover.md",
            "candidate_constraints": constraints,
            "capability_profile_supplied": isinstance(discovery.get("capability_profile"), dict),
            "generic_discovery": {
                "provider": discovery.get("provider"),
                "execution": "EXTERNAL",
                "built_in_web_discovery": False,
                "result_ingest": "career.scan_and_review.discovery.candidates",
                "dedicated_adapters_are_market_boundary": False,
                "official_exact_role_verification": "REQUIRED_WHERE_AVAILABLE",
            },
        },
    }
    return make_handoff(payload, f"MCP-DISCOVERY-{scan_id}", str(created_at)[:10])


def _normalize_discovery_candidate(candidate: dict[str, Any], handoff: dict[str, Any]) -> dict[str, Any]:
    raw = dict(candidate)
    role = str(
        raw.get("role")
        or raw.get("exact_role")
        or raw.get("exactRole")
        or raw.get("role_title")
        or raw.get("market_title")
        or "UNKNOWN"
    ).strip()
    company = str(raw.get("company") or "UNKNOWN").strip()
    if not company or not role or company == "UNKNOWN" or role == "UNKNOWN":
        raise ValueError("generic discovery candidate requires company and exact role")
    role_family = raw.get("role_family") or raw.get("roleFamily") or "UNKNOWN"
    company_coverage_bucket = (
        raw.get("company_coverage_bucket")
        or raw.get("companyCoverageBucket")
        or raw.get("company_type")
        or raw.get("companyType")
        or "UNKNOWN"
    )
    evidence_refs = raw.get("evidence_refs", raw.get("evidenceRefs", []))
    if evidence_refs is None:
        evidence_refs = []
    official_source = raw.get("official_source", raw.get("officialSource"))
    official_source = dict(official_source) if isinstance(official_source, dict) else {}
    official_url = official_source.get("url") or raw.get("official_url") or raw.get("officialUrl")
    if official_url:
        official_source.setdefault("url", official_url)
    official_source.setdefault("exact_role_verified", False)
    official_source.setdefault("inspected_original", False)
    discovery_source = raw.get("discovery_source", raw.get("discoverySource"))
    provenance = raw.get("provenance", [])
    provenance = list(provenance) if isinstance(provenance, list) else []
    if discovery_source and not provenance:
        provenance.append({"kind": "DISCOVERY", "url": discovery_source})
    if official_url and not any(
        isinstance(item, dict) and item.get("url") == official_url for item in provenance
    ):
        provenance.append({"kind": "OFFICIAL_CANDIDATE", "url": official_url})
    live_status = raw.get("live_status", raw.get("liveStatus", "VERIFY"))
    if not isinstance(live_status, str):
        live_status = "VERIFY"
    qualification_facts = raw.get(
        "qualification_facts", raw.get("qualificationFacts", [])
    )
    qualification_facts = (
        list(qualification_facts) if isinstance(qualification_facts, list) else []
    )
    uncertainty = raw.get("uncertainty", [])
    uncertainty = list(uncertainty) if isinstance(uncertainty, list) else []
    for marker, missing in (
        ("OFFICIAL_EXACT_ROLE_NOT_VERIFIED", not (
            official_source.get("exact_role_verified") is True
            and official_source.get("inspected_original") is True
        )),
        ("LIVE_STATUS_VERIFY", live_status in {None, "UNKNOWN", "VERIFY"}),
        ("QUALIFICATION_FACTS_VERIFY", not qualification_facts),
        ("DEADLINE_VERIFY", raw.get("deadline") in {None, "", "UNKNOWN"}),
        (
            "APPLICATION_RULE_VERIFY",
            raw.get("application_rule", raw.get("applicationRule"))
            in {None, "", "UNKNOWN"},
        ),
    ):
        if missing and marker not in uncertainty:
            uncertainty.append(marker)
    why = raw.get("why_matched")
    if not isinstance(why, dict):
        why = {
            "capability": raw.get("strongest_capability_match", "UNKNOWN"),
            "role_family": role_family,
            "market_title": role,
            "matched_role_hypothesis": raw.get("matched_role_hypothesis", "UNKNOWN"),
            "evidence_refs": evidence_refs,
            "responsibility_match": raw.get("responsibility_match", "UNKNOWN"),
            "gaps": raw.get("main_gaps", "UNKNOWN"),
        }
    raw.update(
        {
            "company": company,
            "role": role,
            "location": raw.get("location") or raw.get("city") or "UNKNOWN",
            "official_source": official_source or "UNKNOWN",
            "live_status": live_status,
            "qualification_facts": qualification_facts,
            "deadline": raw.get("deadline") or "UNKNOWN",
            "application_rule": raw.get(
                "application_rule", raw.get("applicationRule", "UNKNOWN")
            ),
            "provenance": provenance,
            "uncertainty": uncertainty,
            "role_family": role_family,
            "company_coverage_bucket": str(company_coverage_bucket).strip().upper(),
            "ai_involvement": raw.get("ai_involvement", raw.get("aiInvolvement", "UNKNOWN")),
            "why_matched": why,
            "evidence_refs": evidence_refs,
            "risk": list(raw.get("risk", raw.get("risks", [])) or []) + ["OFFICIAL_SOURCE_VERIFY_REQUIRED"],
            "next_action": "VERIFY_OFFICIAL_SOURCE",
            "source_url": official_url or discovery_source or raw.get("source_url"),
            "source_type": raw.get("source_type", "GENERIC_DISCOVERY_INPUT"),
            "verification_status": "NEEDS_VERIFY",
            "discovery_only": True,
            "discovery_context": {
                "mode": "market_discovery",
                "handoff_schema_version": handoff.get("schema_version", "UNKNOWN"),
            },
            "screening": {
                "state": "VERIFY",
                "reasons": ["discovery candidate requires official source verification"],
                "role_term_hits": [],
                "capability_term_hits": [],
                "preference_risk_hits": raw.get("risk", []),
                "experience_requirement": {"minimum_years": None, "maximum_years": None, "evidence": None},
                "experience_gap_signal": False,
                "job_quality": {"state": "UNKNOWN", "reason": "Discovery input is not a verified current vacancy."},
                "final_fit_decision": False,
            },
        }
    )
    return raw


def _merge_discovery_candidates(scan: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from scripts.job_scan_batch import SCREENING_ORDER, dedupe_candidates
    except ModuleNotFoundError:
        from job_scan_batch import SCREENING_ORDER, dedupe_candidates

    combined = dedupe_candidates(list(scan.get("candidate_pool") or []) + candidates)
    combined.sort(
        key=lambda row: (
            SCREENING_ORDER.get((row.get("screening") or {}).get("state"), 99),
            str(row.get("company", "")).lower(),
            str(row.get("role", "")).lower(),
        )
    )
    counts: dict[str, int] = {}
    for row in combined:
        state = (row.get("screening") or {}).get("state", "VERIFY")
        counts[state] = counts.get(state, 0) + 1
    merged = dict(scan)
    merged["raw_record_count"] = int(scan.get("raw_record_count", 0)) + len(candidates)
    merged["deduped_count"] = len(combined)
    merged["screening_counts"] = counts
    merged["candidate_pool"] = combined
    return merged


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _configured_scan(career_context: dict[str, Any]) -> dict[str, Any]:
    preset = _load_json(DEFAULT_SCAN_PRESET)
    config = {
        "scan_id": "LIVE-CONFIGURED-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "profile": copy.deepcopy(preset.get("profile") or {}),
        "sources": copy.deepcopy(preset.get("sources") or []),
    }

    # Existing exact Tencent roles are request-scoped Career context, not
    # persisted inside the public source preset.
    if (preset.get("dynamic_sources") or {}).get("existing_tencent_roles"):
        seen = {
            str(url)
            for source in config["sources"]
            for url in (source.get("urls") or ([source.get("url")] if source.get("url") else []))
        }
        for role in career_context.get("existing_roles") or []:
            if str(role.get("company") or "").strip().lower() != "tencent":
                continue
            external_id = str(role.get("external_job_id") or role.get("official_post_id") or "").strip()
            if not external_id.isdigit():
                continue
            url = f"https://join.qq.com/post_detail.html?postid={external_id}"
            if url in seen:
                continue
            config["sources"].append(
                {"adapter": "tencent", "mode": "detail", "urls": [url]}
            )
            seen.add(url)

    return config


def resolve_scan_config(
    scan_config: dict[str, Any] | None,
    career_context: dict[str, Any],
    *,
    use_configured_sources: bool = True,
) -> dict[str, Any]:
    if scan_config is None:
        if not use_configured_sources:
            raise ValueError(
                "scanConfig is required when useConfiguredSources is false"
            )
        return _configured_scan(career_context)
    if not isinstance(scan_config, dict):
        raise ValueError("scanConfig must be an object")
    return copy.deepcopy(scan_config)


def build_summary(
    scan: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    priority = []
    for candidate in scan.get("candidate_pool") or []:
        screening = candidate.get("screening") or {}
        if screening.get("state") == "REVIEW_PRIORITY":
            priority.append(
                {
                    "company": candidate.get("company"),
                    "external_job_id": candidate.get("external_job_id"),
                    "role": candidate.get("role"),
                    "location": candidate.get("location"),
                    "verification_status": candidate.get("verification_status"),
                }
            )

    return {
        "scan_id": scan.get("scan_id"),
        "captured_at": scan.get("captured_at"),
        "source_results": scan.get("source_results"),
        "raw_record_count": scan.get("raw_record_count"),
        "deduped_count": scan.get("deduped_count"),
        "screening_counts": scan.get("screening_counts"),
        "review_packet_count": review.get("review_packet_count"),
        "review_state_counts": review.get("review_state_counts"),
        "review_priority_candidates": priority,
        "external_action": False,
        "human_review_required": True,
    }


def run_scan_review(
    scan_config: dict[str, Any] | None,
    career_context: dict[str, Any] | None,
    *,
    use_configured_sources: bool = True,
    use_current_career_context: bool = True,
    pool_mode: str = "BROAD",
    mode: str = "configured_review",
    discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mode not in SCAN_MODES:
        raise ValueError("mode must be configured_review, market_discovery or hybrid_discovery")
    if mode == "configured_review" and use_configured_sources and scan_config is not None:
        raise ValueError(
            "scanConfig must be omitted when useConfiguredSources is true; "
            "pool mode never changes source scope"
        )
    if mode in {"market_discovery", "hybrid_discovery"} and scan_config is not None:
        raise ValueError("discovery modes do not accept caller scanConfig")
    if use_current_career_context:
        resolved_context = load_current_career_context(career_context or {})
    else:
        resolved_context = copy.deepcopy(career_context or {})

    market_profile = _market_discovery_profile(resolved_context)
    normalized_discovery = _normalize_discovery(discovery)
    captured_at = source_runtime.utc_now()
    resolved = None
    if mode in {"configured_review", "hybrid_discovery"}:
        resolved = resolve_scan_config(
            scan_config,
            resolved_context,
            use_configured_sources=use_configured_sources,
        )
        scope_before = _source_scope(resolved)
        scan = run_batch(resolved)
        scope_after = _source_scope(resolved)
        if scope_before["fingerprint"] != scope_after["fingerprint"]:
            raise RuntimeError("source scope mutated during scan execution")
        captured_at = scan.get("captured_at") or captured_at
    else:
        scope_before = _source_scope({"sources": []})
        scan = _empty_scan(
            f"MCP-DISCOVERY-{captured_at.replace(':', '').replace('+', '')}",
            captured_at,
        )

    discovery_info: dict[str, Any] = {
        "mode": mode,
        "state": "NOT_REQUESTED" if mode == "configured_review" else "NOT_SUPPLIED",
        "generic_provider": {
            "provider": normalized_discovery.get("provider"),
            "execution": "EXTERNAL",
            "built_in_web_discovery": False,
            "result_ingest": "career.scan_and_review.discovery.candidates",
            "dedicated_adapters_are_market_boundary": False,
        },
        "role_hypothesis_count": 0,
        "candidate_count": 0,
        "handoff_schema_version": None,
        "default_profile_id": market_profile.get("profile_id", "UNKNOWN"),
        "coverage": _audit_market_discovery_coverage([], market_profile),
    }
    empty_discovery = _normalize_discovery(None)
    if mode in {"market_discovery", "hybrid_discovery"} and normalized_discovery != empty_discovery:
        raw_candidates = normalized_discovery.get("candidates", [])
        role_hypotheses = normalized_discovery.get("role_hypotheses", [])
        handoff = (
            _make_discovery_handoff(
                normalized_discovery,
                scan.get("scan_id") or "UNKNOWN",
                captured_at,
                market_profile,
            )
            if role_hypotheses
            else None
        )
        if not handoff and not raw_candidates:
            raise ValueError(
                "market discovery requires discovery.roleHypotheses or discovery.candidates"
            )
        ingest_context = handoff or {"schema_version": "0.2.4"}
        discovery_candidates = [
            _normalize_discovery_candidate(candidate, ingest_context)
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]
        coverage = _audit_market_discovery_coverage(
            discovery_candidates,
            market_profile,
            normalized_discovery.get("provider_run") or {},
        )
        scan = _merge_discovery_candidates(scan, discovery_candidates)
        scan.setdefault("source_results", []).append({
            "provider": normalized_discovery.get("provider"),
            "mode": "external_web_handoff",
            "status": "RESULTS_INGESTED" if discovery_candidates else "HANDOFF_REQUIRED",
            "record_count": len(discovery_candidates),
        })
        discovery_info.update(
            {
                "state": "RESULTS_INGESTED" if discovery_candidates else "HANDOFF_REQUIRED",
                "role_hypothesis_count": len(normalized_discovery.get("role_hypotheses", [])),
                "candidate_count": len(discovery_candidates),
                "handoff_schema_version": ingest_context.get("schema_version"),
                "provider_run": normalized_discovery.get("provider_run") or {},
                "coverage": coverage,
                "coverage_state": coverage["state"],
                "continuation_state": (
                    "SUPPLEMENT_REQUIRED"
                    if coverage["supplement_required"]
                    else "COMPLETE_FOR_CURRENT_SCOPE"
                    if discovery_candidates
                    else "HANDOFF_REQUIRED"
                ),
            }
        )
        if coverage["supplement_required"]:
            discovery_info["supplemental_handoff"] = {
                "provider": "EXTERNAL_WEB_DISCOVERY_HANDOFF",
                "trigger": "DISCOVERY_COVERAGE_IMBALANCE",
                "action": "CONTINUE_DISCOVERY_WITHIN_CURRENT_SCOPE",
                "company_coverage_buckets": coverage["supplement_buckets"],
                "reuse_current_role_hypotheses": True,
                "configured_adapters_are_market_boundary": False,
                "human_reapproval_required": False,
                "external_action": False,
            }
        if handoff:
            discovery_info["handoff"] = handoff
    elif mode == "market_discovery":
        raise ValueError("market_discovery requires discovery input")

    review = build_review_packets(scan, resolved_context)
    pool_view = _pool_view(scan, pool_mode)
    summary = build_summary(scan, review)
    summary["pool_mode"] = pool_view["mode"]
    summary["retained_candidate_count"] = pool_view["retained_candidate_count"]
    summary["career_context_source"] = (
        (resolved_context.get("_context_provider") or {}).get("source")
        if use_current_career_context
        else "CALLER_ONLY"
    )
    summary["career_context_version"] = (
        (resolved_context.get("_context_provider") or {}).get("version")
        if use_current_career_context
        else None
    )
    summary["mode"] = mode
    summary["discovery_candidate_count"] = discovery_info["candidate_count"]

    return {
        "schema_version": "0.3",
        "operation": "SCAN_AND_REVIEW",
        "mode": mode,
        "candidate_status": "HUMAN_REVIEW_REQUIRED",
        "scan_config_source": (
            "CURRENT_CONFIGURED_SOURCES" if mode == "configured_review" and scan_config is None
            else "CALLER_SUPPLIED" if mode == "configured_review"
            else "DISCOVERY_INPUT" if mode == "market_discovery"
            else "CURRENT_CONFIGURED_SOURCES_PLUS_DISCOVERY_INPUT"
            if discovery_info["state"] == "RESULTS_INGESTED" else "CURRENT_CONFIGURED_SOURCES"
        ),
        "source_scope": scope_before,
        "pool_view": pool_view,
        "summary": summary,
        "discovery": discovery_info,
        "scan": scan,
        "review": review,
        "boundary": {
            "read_only_public_sources": True,
            "canonical_write": False,
            "application": False,
            "login": False,
            "upload": False,
            "external_contact": False,
            "cv_edit": False,
            "portfolio_edit": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-config")
    parser.add_argument("--career-context")
    parser.add_argument("--no-configured-sources", action="store_true")
    parser.add_argument("--no-current-career-context", action="store_true")
    parser.add_argument("--pool-mode", choices=["BROAD", "FOCUSED"], default="BROAD")
    parser.add_argument("--mode", choices=sorted(SCAN_MODES), default="configured_review")
    parser.add_argument("--discovery")
    parser.add_argument("--output")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only the compact summary; full output is still written with --output.",
    )
    args = parser.parse_args()

    scan_config = _load_json(args.scan_config) if args.scan_config else None
    career_context = _load_json(args.career_context) if args.career_context else {}
    discovery = _load_json(args.discovery) if args.discovery else None
    result = run_scan_review(
        scan_config,
        career_context,
        use_configured_sources=not args.no_configured_sources,
        use_current_career_context=not args.no_current_career_context,
        pool_mode=args.pool_mode,
        mode=args.mode,
        discovery=discovery,
    )

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload)

    visible = result["summary"] if args.summary_only else result
    print(json.dumps(visible, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
