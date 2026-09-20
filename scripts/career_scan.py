"""Single user-facing entrypoint for bounded Career Intelligence job scanning.

One invocation runs public-source scanning, deduplication/triage and the
Career review bridge. It produces review artifacts only. No application,
canonical mutation, login, upload, recruiter contact or material editing.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.career_context_provider import load_current_career_context
    from scripts.job_scan_batch import run_batch
    from scripts.job_scan_review_bridge import build_review_packets
except ModuleNotFoundError:  # direct execution from repository root
    from career_context_provider import load_current_career_context
    from job_scan_batch import run_batch
    from job_scan_review_bridge import build_review_packets


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_PRESET = ROOT / "config/current-job-scan-preset.json"


POOL_RETAIN_STATES = {
    "BROAD": ("REVIEW_PRIORITY", "REVIEW", "VERIFY", "DEPRIORITIZE"),
    "FOCUSED": ("REVIEW_PRIORITY", "REVIEW"),
}


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
            }
            for candidate in rows
        ],
        "source_scope_changed": False,
    }


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
) -> dict[str, Any]:
    if use_configured_sources and scan_config is not None:
        raise ValueError(
            "scanConfig must be omitted when useConfiguredSources is true; "
            "pool mode never changes source scope"
        )
    if use_current_career_context:
        resolved_context = load_current_career_context(career_context or {})
    else:
        resolved_context = copy.deepcopy(career_context or {})

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

    return {
        "schema_version": "0.3",
        "operation": "SCAN_AND_REVIEW",
        "candidate_status": "HUMAN_REVIEW_REQUIRED",
        "scan_config_source": (
            "CURRENT_CONFIGURED_SOURCES" if scan_config is None else "CALLER_SUPPLIED"
        ),
        "source_scope": scope_before,
        "pool_view": pool_view,
        "summary": summary,
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
    parser.add_argument("--output")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only the compact summary; full output is still written with --output.",
    )
    args = parser.parse_args()

    scan_config = _load_json(args.scan_config) if args.scan_config else None
    career_context = _load_json(args.career_context) if args.career_context else {}
    result = run_scan_review(
        scan_config,
        career_context,
        use_configured_sources=not args.no_configured_sources,
        use_current_career_context=not args.no_current_career_context,
        pool_mode=args.pool_mode,
    )

    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload)

    visible = result["summary"] if args.summary_only else result
    print(json.dumps(visible, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
