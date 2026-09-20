"""Multi-source read-only job scan batch for Career Intelligence.

This orchestration layer discovers and verifies public jobs through the existing
source runtime, deduplicates records, and adds transparent first-pass screening
signals. It does not make a final fit decision or perform any external action.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts import job_source_runtime as source_runtime
except ModuleNotFoundError:  # direct script execution from repository root
    import job_source_runtime as source_runtime


SCREENING_ORDER = {
    "REVIEW_PRIORITY": 0,
    "REVIEW": 1,
    "VERIFY": 2,
    "DEPRIORITIZE": 3,
    "CLOSE": 4,
}


class ScanConfigError(ValueError):
    """Raised when a caller supplies an invalid scan contract."""


def validate_scan_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ScanConfigError("scanConfig must be an object")
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ScanConfigError(
            "scanConfig.sources must be a non-empty array; omit scanConfig to use configured sources"
        )
    for index, source in enumerate(sources):
        prefix = f"scanConfig.sources[{index}]"
        if not isinstance(source, dict):
            raise ScanConfigError(f"{prefix} must be an object")
        adapter = source.get("adapter")
        if adapter not in source_runtime.ADAPTERS:
            raise ScanConfigError(
                f"{prefix}.adapter must be one of: {', '.join(sorted(source_runtime.ADAPTERS))}"
            )
        mode = source.get("mode", "discover")
        if mode not in {"discover", "detail"}:
            raise ScanConfigError(f"{prefix}.mode must be discover or detail")
        if mode == "discover" and not source.get("url"):
            raise ScanConfigError(f"{prefix}.url is required for discover mode")
        if mode == "detail":
            urls = source.get("urls")
            if not source.get("url") and not (
                isinstance(urls, list) and any(str(item).strip() for item in urls)
            ):
                raise ScanConfigError(
                    f"{prefix} requires url or non-empty urls for detail mode"
                )
        for field in ("limit", "verify_limit"):
            if field not in source:
                continue
            value = source[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 100:
                raise ScanConfigError(f"{prefix}.{field} must be an integer from 0 to 100")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_text(item) for item in value)
    return str(value)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip().lower()


def _matches(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for term in terms:
        needle = term.lower()
        if not needle:
            continue
        # Short ASCII concepts such as "AI" must match as tokens. Plain
        # substring matching would incorrectly treat "China" as an AI signal.
        if needle.isascii() and len(needle) <= 3 and needle.isalnum():
            if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered):
                hits.append(term)
        elif needle in lowered:
            hits.append(term)
    return hits


def _location_text(record: dict[str, Any]) -> str:
    return _norm(record.get("location"))


def _experience_requirement(text: str) -> dict[str, Any]:
    patterns = (
        r"(\d+)\s*[~～\-—至到]\s*(\d+)\s*年",
        r"(\d+)\s*年(?:及)?以上",
        r"(\d+)\+\s*years?",
        r"(\d+)\s*(?:or more|plus)\s*years?",
    )
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        if index == 0:
            minimum, maximum = int(match.group(1)), int(match.group(2))
        else:
            minimum, maximum = int(match.group(1)), None
        return {
            "minimum_years": minimum,
            "maximum_years": maximum,
            "evidence": match.group(0),
        }
    return {"minimum_years": None, "maximum_years": None, "evidence": None}


def candidate_identity(record: dict[str, Any]) -> str:
    company = _norm(record.get("company"))
    external = _norm(record.get("external_job_id"))
    if company and external:
        return f"{company}:external:{external}"
    source = _norm(record.get("source_identity") or record.get("source_url"))
    if source:
        return f"{company}:source:{source}"
    role = _norm(record.get("role"))
    location = _location_text(record)
    return f"{company}:fallback:{role}:{location}"


def _verification_rank(status: str | None) -> int:
    return {
        "OPEN_VERIFIED": 3,
        "CLOSED": 3,
        "NEEDS_VERIFY": 1,
    }.get(status or "", 0)


def dedupe_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        key = candidate_identity(record)
        if key not in merged:
            merged[key] = dict(record)
            merged[key]["dedupe_identity"] = key
            merged[key]["duplicate_count"] = 1
            order.append(key)
            continue
        current = merged[key]
        current["duplicate_count"] = int(current.get("duplicate_count", 1)) + 1
        if _verification_rank(record.get("verification_status")) > _verification_rank(
            current.get("verification_status")
        ):
            duplicate_count = current["duplicate_count"]
            merged[key] = dict(record)
            merged[key]["dedupe_identity"] = key
            merged[key]["duplicate_count"] = duplicate_count
    return [merged[key] for key in order]


def screen_record(
    record: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    role_text = _norm(record.get("role"))
    body_text = _norm(
        " ".join(
            [
                _text(record.get("role")),
                _text(record.get("responsibilities")),
                _text(record.get("requirements")),
                _text(record.get("department")),
                _text(record.get("recruitment_project")),
                _text(record.get("recruitment_label")),
                _text(record.get("career_status")),
                _text(record.get("graduate_bonus")),
            ]
        )
    )
    location_text = _location_text(record)

    preferred_locations = profile.get("preferred_locations", [])
    deprioritized_locations = profile.get("deprioritized_locations", [])
    role_terms = profile.get("role_terms", [])
    capability_terms = profile.get("capability_terms", [])
    risk_terms = profile.get("risk_terms", [])
    student_terms = profile.get(
        "student_terms",
        ["应届", "在读", "实习", "graduate", "intern", "student"],
    )

    preferred_hits = _matches(location_text, preferred_locations)
    deprioritized_hits = _matches(location_text, deprioritized_locations)
    role_hits = _matches(role_text, role_terms)
    capability_hits = _matches(body_text, capability_terms)
    risk_hits = _matches(body_text, risk_terms)
    student_hits = _matches(body_text, student_terms)
    experience = _experience_requirement(body_text)
    max_experience = profile.get("max_experience_years")

    experience_gap = bool(
        isinstance(max_experience, int)
        and experience["minimum_years"] is not None
        and experience["minimum_years"] > max_experience
    )

    status = record.get("verification_status")
    if status == "CLOSED":
        state = "CLOSE"
        reasons = ["official source indicates vacancy is closed"]
    elif status != "OPEN_VERIFIED":
        state = "VERIFY"
        reasons = ["vacancy status still needs official verification"]
    elif risk_hits:
        state = "DEPRIORITIZE"
        reasons = ["explicit preference-risk terms found"]
    elif experience_gap:
        state = "DEPRIORITIZE"
        reasons = ["experience requirement exceeds configured early-career bound"]
    elif not role_hits and not capability_hits:
        state = "DEPRIORITIZE"
        reasons = ["no configured role-family or capability signal found"]
    elif preferred_hits and role_hits and capability_hits:
        state = "REVIEW_PRIORITY"
        reasons = ["preferred-location, role and capability signals all present"]
    elif deprioritized_hits and not capability_hits:
        state = "DEPRIORITIZE"
        reasons = ["deprioritized location without compensating capability signal"]
    else:
        state = "REVIEW"
        reasons = ["source is open but requires Career Intelligence review"]

    screened = dict(record)
    screened["screening"] = {
        "state": state,
        "reasons": reasons,
        "location": {
            "preferred_hits": preferred_hits,
            "deprioritized_hits": deprioritized_hits,
        },
        "role_term_hits": role_hits,
        "capability_term_hits": capability_hits,
        "preference_risk_hits": risk_hits,
        "student_or_early_career_hits": student_hits,
        "experience_requirement": experience,
        "experience_gap_signal": experience_gap,
        "job_quality": {
            "state": "UNKNOWN",
            "reason": (
                "Public vacancy text alone does not establish workload, leave, "
                "management quality, compensation reliability, or stability."
            ),
        },
        "final_fit_decision": False,
    }
    return screened


def _discover_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    result = source_runtime.discover(
        source["adapter"],
        source["url"],
        limit=int(source.get("limit", 20)),
        query=source.get("query"),
        location=source.get("location"),
    )
    candidates = result.get("candidates") or []
    verify_limit = max(0, int(source.get("verify_limit", len(candidates))))
    discovery_context = {
        "adapter": source.get("adapter"),
        "source_url": source.get("url"),
        "query": source.get("query"),
        "location": source.get("location"),
    }
    verified: list[dict[str, Any]] = []
    for candidate in candidates[:verify_limit]:
        url = candidate.get("source_url")
        if not url:
            detail = dict(candidate)
        else:
            try:
                detail = source_runtime.extract(source["adapter"], url)
            except Exception as exc:  # preserve the lead instead of inventing closure
                detail = dict(candidate)
                detail["verification_status"] = "NEEDS_VERIFY"
                detail["verification_error"] = type(exc).__name__
        detail["discovery_context"] = discovery_context
        verified.append(detail)
    for candidate in candidates[verify_limit:]:
        pending = dict(candidate)
        pending["discovery_context"] = discovery_context
        verified.append(pending)
    return verified


def _detail_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    urls = source.get("urls") or ([source["url"]] if source.get("url") else [])
    records: list[dict[str, Any]] = []
    for url in urls:
        try:
            records.append(source_runtime.extract(source["adapter"], url))
        except Exception as exc:
            records.append(
                {
                    "company": source.get("company"),
                    "adapter_name": source["adapter"],
                    "source_url": url,
                    "verification_status": "NEEDS_VERIFY",
                    "verification_error": type(exc).__name__,
                }
            )
    return records


def run_batch(config: dict[str, Any]) -> dict[str, Any]:
    validate_scan_config(config)
    profile = config.get("profile") or {}
    records: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    for source in config.get("sources", []):
        mode = source.get("mode", "discover")
        try:
            batch = (
                _discover_source(source)
                if mode == "discover"
                else _detail_source(source)
            )
            records.extend(batch)
            source_results.append(
                {
                    "adapter": source.get("adapter"),
                    "mode": mode,
                    "status": "OK",
                    "record_count": len(batch),
                }
            )
        except Exception as exc:
            source_results.append(
                {
                    "adapter": source.get("adapter"),
                    "mode": mode,
                    "status": "ERROR",
                    "error": type(exc).__name__,
                }
            )

    deduped = dedupe_candidates(records)
    screened = [screen_record(record, profile) for record in deduped]
    screened.sort(
        key=lambda row: (
            SCREENING_ORDER.get(row["screening"]["state"], 99),
            _norm(row.get("company")),
            _norm(row.get("role")),
        )
    )

    counts: dict[str, int] = {}
    for row in screened:
        state = row["screening"]["state"]
        counts[state] = counts.get(state, 0) + 1

    return {
        "scan_id": config.get("scan_id"),
        "captured_at": source_runtime.utc_now(),
        "source_results": source_results,
        "raw_record_count": len(records),
        "deduped_count": len(deduped),
        "screening_counts": counts,
        "candidate_pool": screened,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    result = run_batch(config)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
