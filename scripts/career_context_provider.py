"""Read-only current Career context provider.

The public Career Intelligence core stays reusable. User-specific Career state
lives outside the repository and is loaded read-only at execution time.
Request-scoped overlays may add context, but they cannot silently delete exact
roles from the current local context snapshot.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONTEXT_PATH = Path.home() / (
    "Library/Application Support/Career Intelligence/context/"
    "current-career-context.json"
)


class CareerContextError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CareerContextError(
            "current Career context is unavailable; refresh the local Career "
            "context snapshot instead of reconstructing it from chat memory"
        )
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise CareerContextError("current Career context must be a JSON object")
    return payload


def _role_key(role: dict[str, Any]) -> str:
    company = str(role.get("company") or "").strip().lower()
    external = str(
        role.get("external_job_id")
        or role.get("official_post_id")
        or role.get("role_id")
        or ""
    ).strip().lower()
    if company and external:
        return f"{company}:external:{external}"
    source = str(role.get("source_identity") or role.get("source_url") or "").strip().lower()
    if company and source:
        return f"{company}:source:{source}"
    title = str(role.get("role") or "").strip().lower()
    return f"{company}:title:{title}"


def _merge_roles(
    base_roles: list[dict[str, Any]],
    overlay_roles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for role in [*base_roles, *overlay_roles]:
        if not isinstance(role, dict):
            continue
        key = _role_key(role)
        if key not in merged:
            merged[key] = copy.deepcopy(role)
            order.append(key)
        else:
            merged[key].update(copy.deepcopy(role))
    return [merged[key] for key in order]


def _merge_constraints(
    base: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for company, items in overlay.items():
        existing = result.setdefault(company, [])
        if not isinstance(existing, list):
            existing = []
            result[company] = existing
        for item in items if isinstance(items, list) else []:
            if item not in existing:
                existing.append(copy.deepcopy(item))
    return result


def _merge_context(
    base: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if key == "existing_roles":
            result[key] = _merge_roles(
                result.get(key) or [],
                value if isinstance(value, list) else [],
            )
        elif key in {"preference_context", "candidate_context"}:
            current = result.get(key)
            current = current if isinstance(current, dict) else {}
            update = value if isinstance(value, dict) else {}
            result[key] = {**copy.deepcopy(current), **copy.deepcopy(update)}
        elif key == "company_constraints":
            result[key] = _merge_constraints(
                result.get(key) or {},
                value if isinstance(value, dict) else {},
            )
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_current_career_context(
    overlay: dict[str, Any] | None = None,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    configured = Path(
        path
        or os.environ.get("CAREER_CONTEXT_PATH")
        or DEFAULT_CONTEXT_PATH
    ).expanduser()
    base = _load_json(configured)
    if overlay:
        base = _merge_context(base, overlay)

    metadata = base.setdefault("_context_provider", {})
    metadata.update(
        {
            "source": "CURRENT_LOCAL_CONTEXT",
            "version": base.get("context_version"),
            "as_of": base.get("as_of"),
            "existing_role_count": len(base.get("existing_roles") or []),
            "read_only": True,
            "canonical_write": False,
        }
    )
    return base


def context_status(*, path: str | Path | None = None) -> dict[str, Any]:
    context = load_current_career_context(path=path)
    provider = context["_context_provider"]
    return {
        "source": provider["source"],
        "version": provider["version"],
        "as_of": provider["as_of"],
        "existing_role_count": provider["existing_role_count"],
        "read_only": True,
        "canonical_write": False,
    }
