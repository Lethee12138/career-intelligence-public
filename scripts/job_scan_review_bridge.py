"""Bridge a scan Candidate Pool into Career Intelligence review packets.

The bridge is intentionally non-semantic: it preserves exact job/source facts,
candidate-context references, existing-pool continuity and analysis gates. Final
Capability/Eligibility/Preference/Quality judgments belong to /analyse-job.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REVIEW_STATES = ("REVIEW_PRIORITY", "REVIEW")


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def exact_role_key(candidate: dict[str, Any]) -> str:
    company = _norm(candidate.get("company"))
    external_id = _norm(candidate.get("external_job_id"))
    if company and external_id:
        return f"{company}:external:{external_id}"
    source = _norm(candidate.get("source_identity") or candidate.get("source_url"))
    if source:
        return f"{company}:source:{source}"
    return f"{company}:unbound:{_norm(candidate.get('role'))}"


def _existing_index(existing_roles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for role in existing_roles:
        key = role.get("exact_role_key")
        if not key:
            key = exact_role_key(role)
        if key:
            index[str(key).lower()] = role
    return index


def _split_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value)
    rows: list[str] = []
    for chunk in text.replace("\r", "\n").split("\n"):
        item = chunk.strip()
        if item:
            rows.append(item)
    return rows


def _qualification_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    status = candidate.get("verification_status")
    screening = candidate.get("screening") or {}
    if status != "OPEN_VERIFIED":
        return {
            "state": "SOURCE_VERIFY_FIRST",
            "reason": "Current official OPEN status is not fully verified.",
        }
    requirements = " ".join(_split_lines(candidate.get("requirements"))).lower()
    role_title = str(candidate.get("role") or "").lower()
    gate_markers: list[str] = []
    if "实习" in role_title or "intern" in role_title:
        gate_markers.append("INTERNSHIP_ROUTE")
    for label, terms in (
        ("INTERNSHIP_DURATION_OR_ATTENDANCE", ("连续实习", "每周出勤", "internship duration")),
        ("EXPERIENCE_REQUIREMENT", ("年以上", "years of experience", "year of experience")),
        ("STUDENT_STATUS", ("在读", "应届", "graduate", "student")),
        ("TOOL_OR_QUANT_REQUIREMENT", ("sql", "ab实验", "a/b", "定量")),
        ("LANGUAGE_REQUIREMENT", ("英语四级", "cet-4", "cet4")),
    ):
        if any(term in requirements for term in terms):
            gate_markers.append(label)
    if screening.get("experience_gap_signal"):
        gate_markers.append("EARLY_CAREER_EXPERIENCE_GAP_SIGNAL")
    if gate_markers:
        return {
            "state": "QUALIFICATION_REVIEW_REQUIRED",
            "reason": "Visible requirements include candidate-specific gates or unresolved requirements.",
            "markers": sorted(set(gate_markers)),
        }
    return {
        "state": "READY_FOR_JOB_ANALYSIS",
        "reason": "Official source is open and no obvious candidate-specific hard gate was auto-resolved.",
        "markers": [],
    }


def build_review_packets(
    scan: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    selected_states = tuple(context.get("review_states") or DEFAULT_REVIEW_STATES)
    existing = _existing_index(context.get("existing_roles") or [])
    packets: list[dict[str, Any]] = []

    for candidate in scan.get("candidate_pool") or []:
        screening = candidate.get("screening") or {}
        if screening.get("state") not in selected_states:
            continue

        role_key = exact_role_key(candidate)
        existing_role = existing.get(role_key.lower())
        gate = _qualification_gate(candidate)

        if existing_role:
            review_state = "EXISTING_POOL_CONTINUITY"
            next_step = "REUSE_EXISTING_ROLE_STATE"
        elif gate["state"] == "SOURCE_VERIFY_FIRST":
            review_state = "SOURCE_VERIFY_FIRST"
            next_step = "VERIFY_SOURCE"
        elif gate["state"] == "QUALIFICATION_REVIEW_REQUIRED":
            review_state = "QUALIFICATION_REVIEW_REQUIRED"
            next_step = "RUN_BOUNDED_QUALIFICATION_REVIEW"
        else:
            review_state = "READY_FOR_JOB_ANALYSIS"
            next_step = "RUN_ANALYSE_JOB"

        packets.append(
            {
                "role_key": role_key,
                "review_state": review_state,
                "next_step": next_step,
                "job_identity": {
                    "company": candidate.get("company"),
                    "external_job_id": candidate.get("external_job_id"),
                    "role": candidate.get("role"),
                    "location": candidate.get("location"),
                    "source_url": candidate.get("source_url"),
                    "source_identity": candidate.get("source_identity"),
                },
                "source": {
                    "source_type": candidate.get("source_type"),
                    "authority_level": candidate.get("authority_level"),
                    "captured_at": candidate.get("captured_at"),
                    "verification_status": candidate.get("verification_status"),
                    "discovery_context": candidate.get("discovery_context"),
                },
                "job_text": {
                    "responsibilities": _split_lines(candidate.get("responsibilities")),
                    "requirements": _split_lines(candidate.get("requirements")),
                    "department": candidate.get("department"),
                    "recruitment_project": candidate.get("recruitment_project"),
                    "recruitment_label": candidate.get("recruitment_label"),
                    "position_nature": candidate.get("position_nature"),
                },
                "scan_screening": screening,
                "qualification_gate": gate,
                "candidate_context": context.get("candidate_context"),
                "preference_context": context.get("preference_context"),
                "company_constraints": (
                    context.get("company_constraints") or {}
                ).get(candidate.get("company"), []),
                "existing_role": existing_role,
                "analysis_contract": {
                    "required_dimensions": [
                        "Capability Fit",
                        "Evidence Fit",
                        "Experience Fit",
                        "Eligibility Fit",
                        "Practical Fit",
                        "Career Value",
                        "Interest / Preference Fit",
                        "Work-style Preference Fit",
                        "Interview Process Risk",
                        "Stretch Level",
                    ],
                    "job_quality_required": True,
                    "no_match_percentage": True,
                    "final_human_review_required": True,
                },
            }
        )

    counts: dict[str, int] = {}
    for packet in packets:
        state = packet["review_state"]
        counts[state] = counts.get(state, 0) + 1

    return {
        "schema_version": "0.1",
        "candidate_status": "HUMAN_REVIEW_REQUIRED",
        "scan_ref": scan.get("scan_id"),
        "scan_captured_at": scan.get("captured_at"),
        "context_as_of": (context.get("candidate_context") or {}).get("as_of"),
        "review_packet_count": len(packets),
        "review_state_counts": counts,
        "packets": packets,
        "boundary": {
            "new_ssot": False,
            "canonical_write": False,
            "application": False,
            "cv_edit": False,
            "portfolio_edit": False,
            "external_contact": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    scan = json.loads(Path(args.scan).read_text())
    context = json.loads(Path(args.context).read_text())
    result = build_review_packets(scan, context)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
