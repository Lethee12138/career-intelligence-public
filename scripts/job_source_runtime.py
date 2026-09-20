"""Read-only public job source runtime for Career Intelligence.

Standard-library only. This module fetches public job pages and normalizes source
facts. It never logs in, submits applications, uploads files, or decides fit.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import ipaddress
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


MAX_BYTES = 5_000_000
USER_AGENT = "CareerIntelligence-JobScanner/0.3 (+public-read-only)"


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    company: str
    verified_hosts: tuple[str, ...]
    runtime_status: str = "ACTIVE"


ADAPTERS = {
    "sap": AdapterSpec("sap", "SAP", ("jobs.sap.com", "careers.sap.com")),
    "tencent": AdapterSpec("tencent", "Tencent", ("join.qq.com",), "DETAIL_ACTIVE"),
    "kuaishou": AdapterSpec(
        "kuaishou", "Kuaishou", ("zhaopin.kuaishou.cn",), "SOCIAL_ACTIVE"
    ),
}

KUAISHOU_PUBLIC_SIGNING_KEY = "652f962a-0575-4575-98d2-f04e2291bee2"
KUAISHOU_READ_ONLY_PATHS = {
    "/recruit/e/api/v1/open/position",
    "/recruit/e/api/v1/open/positions/simple",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_space(value: str | None) -> str | None:
    if value is None:
        return None
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def _host_allowed(host: str, spec: AdapterSpec) -> bool:
    host = host.lower().rstrip(".")
    return any(host == allowed or host.endswith("." + allowed)
               for allowed in spec.verified_hosts)


def _validate_public_url(url: str, spec: AdapterSpec) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only public HTTPS URLs are supported")
    if not spec.verified_hosts:
        raise ValueError(f"{spec.name} live host is not verified yet")
    if not _host_allowed(parsed.hostname, spec):
        raise ValueError(f"Host is outside verified {spec.name} official hosts")
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or
               ip.is_reserved or ip.is_multicast):
        raise ValueError("Private or reserved network targets are not allowed")


def fetch_public(url: str, spec: AdapterSpec, timeout: int = 20) -> tuple[str, str]:
    _validate_public_url(url, spec)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(req, timeout=timeout) as response:
        final_url = response.geturl()
        _validate_public_url(final_url, spec)
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Page exceeds read-only fetch size limit")
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "replace"), final_url


def fetch_json(
    url: str,
    spec: AdapterSpec,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[dict[str, Any], str]:
    _validate_public_url(url, spec)
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)
    req = Request(url, headers=request_headers, method="GET")
    with urlopen(req, timeout=timeout) as response:
        final_url = response.geturl()
        _validate_public_url(final_url, spec)
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Response exceeds read-only fetch size limit")
        charset = response.headers.get_content_charset() or "utf-8"
    payload = json.loads(raw.decode(charset, "replace"))
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object from official source")
    return payload, final_url


def _canonical_query(params: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in sorted(params):
        value = params[key]
        values = value if isinstance(value, (list, tuple)) else [value]
        values = sorted(
            str(item) for item in values if item is not None and str(item) != ""
        )
        if not values:
            continue
        encoded = ",".join(quote_plus(item, safe="~()*!.'") for item in values)
        parts.append(f"{key}={encoded}")
    return "&".join(parts)


def kuaishou_sign(
    params: dict[str, Any],
    timestamp_ms: int,
    key: str = KUAISHOU_PUBLIC_SIGNING_KEY,
) -> str:
    message = f"{timestamp_ms}{_canonical_query(params)}{key}"
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def _kuaishou_open_json(
    path: str,
    params: dict[str, Any],
    timestamp_ms: int | None = None,
) -> tuple[dict[str, Any], str]:
    if path not in KUAISHOU_READ_ONLY_PATHS:
        raise ValueError("Kuaishou runtime only permits approved public read-only endpoints")
    timestamp_ms = timestamp_ms or int(time.time() * 1000)
    query = urlencode(params, doseq=True)
    url = f"https://zhaopin.kuaishou.cn{path}"
    if query:
        url += "?" + query
    headers = {
        "Referer": "https://zhaopin.kuaishou.cn/recruit/e/",
        "sign": kuaishou_sign(params, timestamp_ms),
        "signTimestamp": str(timestamp_ms),
    }
    return fetch_json(url, ADAPTERS["kuaishou"], headers=headers)


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\b{name}=["\']([^"\']+)["\']', tag, re.I)
    return html.unescape(m.group(1)) if m else None


def extract_sap_search(page: str, base_url: str, limit: int = 25) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r"(<a\b[^>]*>)(.*?)</a>", page, re.I | re.S):
        tag, body = match.groups()
        classes = (_attr(tag, "class") or "").split()
        if not any("jobTitle-link" in c for c in classes):
            continue
        href = _attr(tag, "href")
        role = _normalize_space(body)
        if not href or not role:
            continue
        source_url = urljoin(base_url, href)
        source_url = html.unescape(source_url)
        if source_url in seen:
            continue
        seen.add(source_url)
        page_id = None
        m = re.search(r"/(\d+)/?$", urlparse(source_url).path)
        if m:
            page_id = m.group(1)
        found.append({
            "company": "SAP",
            "role": role,
            "source_url": source_url,
            "source_type": "official",
            "authority_level": "HIGH",
            "adapter_name": "sap",
            "source_page_id": page_id,
            "verification_status": "NEEDS_VERIFY",
        })
        if len(found) >= limit:
            break
    return found


def _sap_property(page: str, property_id: str) -> str | None:
    pattern = (
        rf'<span\b[^>]*data-careersite-propertyid=["\']'
        rf'{re.escape(property_id)}["\'][^>]*>(.*?)</span>'
    )
    m = re.search(pattern, page, re.I | re.S)
    return _normalize_space(m.group(1)) if m else None


def extract_sap_detail(page: str, source_url: str, captured_at: str | None = None) -> dict[str, Any]:
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", page, re.I | re.S)
    role = _normalize_space(title_match.group(1)) if title_match else None
    requisition_id = _sap_property(page, "facility")
    location = _sap_property(page, "location")
    department = _sap_property(page, "department")
    posted_date = _sap_property(page, "date")
    career_status = _sap_property(page, "customfield3")
    employment_type = _sap_property(page, "shifttype")
    lowered = _normalize_space(page) or ""
    lowered = lowered.lower()
    closed_markers = (
        "job is no longer available",
        "position is no longer available",
        "this job has expired",
    )
    closed = any(marker in lowered for marker in closed_markers)
    apply_cta = bool(re.search(r'id=["\']apply-CTA-container["\']', page, re.I))
    if not apply_cta:
        apply_cta = bool(re.search(r">\s*apply(?: now)?\s*<", page, re.I))

    if closed:
        status = "CLOSED"
    elif role and requisition_id and location and apply_cta:
        status = "OPEN_VERIFIED"
    else:
        status = "NEEDS_VERIFY"

    return {
        "source_identity": f"career-url:{source_url}",
        "company": "SAP",
        "url": source_url,
        "source_url": source_url,
        "source_type": "official",
        "authority_level": "HIGH",
        "captured_at": captured_at or utc_now(),
        "adapter_name": "sap",
        "extraction_method": "official-html",
        "external_job_id": requisition_id,
        "role": role,
        "location": location,
        "department": department,
        "posted_date": posted_date,
        "career_status": career_status,
        "employment_type": employment_type,
        "verification_status": status,
        "verification_evidence": {
            "detail_page_accessible": bool(role),
            "apply_cta_present": apply_cta,
            "closed_marker_present": closed,
        },
    }


def extract_tencent_payload(
    payload: dict[str, Any],
    source_url: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    data = payload.get("data") if payload.get("status") == 0 else None
    data = data if isinstance(data, dict) else {}
    bg_list = data.get("intentionBGDList") or []
    business_groups = [
        item.get("showTitle") or item.get("title")
        for item in bg_list
        if isinstance(item, dict) and (item.get("showTitle") or item.get("title"))
    ]
    role = data.get("title")
    post_id = str(data.get("postId") or "") or None
    locations = data.get("workCityList") or []
    status = "OPEN_VERIFIED" if role and post_id and locations else "NEEDS_VERIFY"
    return {
        "source_identity": f"career-url:{source_url}",
        "company": "Tencent",
        "url": source_url,
        "source_url": source_url,
        "source_type": "official",
        "authority_level": "HIGH",
        "captured_at": captured_at or utc_now(),
        "adapter_name": "tencent",
        "extraction_method": "official-json-api",
        "external_job_id": post_id,
        "role": role,
        "location": locations,
        "department": data.get("tidName"),
        "business_groups": business_groups,
        "responsibilities": data.get("desc"),
        "requirements": data.get("request"),
        "recruitment_project": data.get("projectName"),
        "recruitment_label": data.get("recruitLabelName"),
        "graduate_bonus": data.get("graduateBonus"),
        "verification_status": status,
        "verification_evidence": {
            "api_status": payload.get("status"),
            "detail_record_present": bool(data),
        },
    }


def fetch_tencent_detail(
    source_url: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    _validate_public_url(source_url, ADAPTERS["tencent"])
    parsed = urlparse(source_url)
    post_ids = parse_qs(parsed.query).get("postid", [])
    if not post_ids or not post_ids[0].isdigit():
        raise ValueError("Tencent detail URL must contain a numeric postid")
    post_id = post_ids[0]
    api_url = (
        "https://join.qq.com/api/v1/jobDetails/getJobDetailsByPostId?"
        + urlencode({"postId": post_id})
    )
    payload, api_final = fetch_json(api_url, ADAPTERS["tencent"])
    record = extract_tencent_payload(payload, source_url, captured_at)
    record["verification_evidence"]["api_url"] = api_final
    return record


def _kuaishou_source_url(job_id: Any) -> str:
    return (
        "https://zhaopin.kuaishou.cn/recruit/e/"
        f"#/official/social/job-info/{job_id}"
    )


def normalize_kuaishou_item(
    item: dict[str, Any],
    verified: bool = False,
    captured_at: str | None = None,
) -> dict[str, Any]:
    job_id = item.get("id")
    source_url = _kuaishou_source_url(job_id)
    locations = item.get("workLocationsCode") or []
    if not locations and item.get("workLocationCode"):
        locations = [item.get("workLocationCode")]
    return {
        "source_identity": f"career-url:{source_url}",
        "company": "Kuaishou",
        "url": source_url,
        "source_url": source_url,
        "source_type": "official",
        "authority_level": "HIGH",
        "captured_at": captured_at or utc_now(),
        "adapter_name": "kuaishou",
        "extraction_method": "official-signed-json-api",
        "external_job_id": str(job_id) if job_id is not None else None,
        "role": item.get("name"),
        "location": locations,
        "department": item.get("departmentName") or item.get("departmentCode"),
        "responsibilities": item.get("description"),
        "requirements": item.get("positionDemand"),
        "recruitment_project": item.get("recruitProjectCode"),
        "position_nature": item.get("positionNatureCode"),
        "updated_at": item.get("updateTime"),
        "verification_status": "OPEN_VERIFIED" if verified else "NEEDS_VERIFY",
    }


def discover_kuaishou(
    query: str | None,
    location: str | None,
    limit: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "pageNum": 1,
        "pageSize": max(1, min(limit, 100)),
        "workLocationCode": location or "domestic",
    }
    if query:
        params["name"] = query
    payload, api_url = _kuaishou_open_json(
        "/recruit/e/api/v1/open/positions/simple", params
    )
    result = payload.get("result") if payload.get("code") == 0 else {}
    result = result if isinstance(result, dict) else {}
    items = result.get("list") or []
    candidates = [
        normalize_kuaishou_item(item)
        for item in items[:limit]
        if isinstance(item, dict)
    ]
    return {
        "adapter": "kuaishou",
        "source_url": "https://zhaopin.kuaishou.cn/recruit/e/",
        "source_api_url": api_url,
        "captured_at": utc_now(),
        "count": len(candidates),
        "reported_total": result.get("total"),
        "candidates": candidates,
    }


def fetch_kuaishou_detail(
    source_url: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    _validate_public_url(source_url, ADAPTERS["kuaishou"])
    match = re.search(r"/job-info/(\d+)", source_url)
    if not match:
        query_ids = parse_qs(urlparse(source_url).query).get("id", [])
        job_id = query_ids[0] if query_ids else None
    else:
        job_id = match.group(1)
    if not job_id or not str(job_id).isdigit():
        raise ValueError("Kuaishou detail URL must contain a numeric job id")
    payload, api_url = _kuaishou_open_json(
        "/recruit/e/api/v1/open/position", {"id": str(job_id)}
    )
    result = payload.get("result") if payload.get("code") == 0 else None
    if not isinstance(result, dict):
        return {
            "source_identity": f"career-url:{source_url}",
            "company": "Kuaishou",
            "source_url": source_url,
            "source_type": "official",
            "authority_level": "HIGH",
            "captured_at": captured_at or utc_now(),
            "adapter_name": "kuaishou",
            "external_job_id": str(job_id),
            "verification_status": "NEEDS_VERIFY",
            "source_state": "NOT_FOUND",
            "verification_evidence": {
                "api_code": payload.get("code"),
                "api_message": payload.get("message"),
                "api_url": api_url,
            },
        }
    record = normalize_kuaishou_item(result, verified=True, captured_at=captured_at)
    record["verification_evidence"] = {
        "api_code": payload.get("code"),
        "detail_record_present": True,
        "api_url": api_url,
    }
    return record


def discover(
    adapter: str,
    url: str,
    limit: int = 25,
    query: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    if adapter == "kuaishou":
        return discover_kuaishou(query, location, limit)
    if adapter != "sap":
        raise NotImplementedError(f"{adapter} discovery parser is not live yet")
    spec = ADAPTERS[adapter]
    page, final_url = fetch_public(url, spec)
    items = extract_sap_search(page, final_url, limit=limit)
    return {
        "adapter": adapter,
        "source_url": final_url,
        "captured_at": utc_now(),
        "count": len(items),
        "candidates": items,
    }


def extract(adapter: str, url: str, captured_at: str | None = None) -> dict[str, Any]:
    if adapter == "tencent":
        return fetch_tencent_detail(url, captured_at=captured_at)
    if adapter == "kuaishou":
        return fetch_kuaishou_detail(url, captured_at=captured_at)
    if adapter != "sap":
        raise NotImplementedError(f"{adapter} detail parser is not live yet")
    spec = ADAPTERS[adapter]
    page, final_url = fetch_public(url, spec)
    return extract_sap_detail(page, final_url, captured_at=captured_at)


def adapter_map(adapter: str) -> dict[str, Any]:
    spec = ADAPTERS[adapter]
    return {
        "adapter": spec.name,
        "company": spec.company,
        "verified_hosts": list(spec.verified_hosts),
        "runtime_status": spec.runtime_status,
        "boundary": "SOURCE_FACTS_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("discover", "extract", "map"))
    parser.add_argument("--adapter", required=True, choices=sorted(ADAPTERS))
    parser.add_argument("--url")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--query")
    parser.add_argument("--location")
    parser.add_argument("--captured-at")
    args = parser.parse_args()

    if args.action == "map":
        result = adapter_map(args.adapter)
    else:
        if not args.url:
            parser.error("--url is required for discover/extract")
        result = (
            discover(
                args.adapter,
                args.url,
                args.limit,
                query=args.query,
                location=args.location,
            )
            if args.action == "discover"
            else extract(args.adapter, args.url, args.captured_at)
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
