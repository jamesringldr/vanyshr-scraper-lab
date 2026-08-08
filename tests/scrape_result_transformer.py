"""
Result Transformer — Convert real scraper responses to DB schema format
==========================================================================

Each scraper's real response shape is different:
  - FPS (service.py):        single object, QuickScanProfileData shape
  - Zaba (workers/zaba):     residential HTTP service — same pattern as FPS
  - Anywho (universal-search): { profiles: ProfileMatch[] }, one row per match

This module normalizes both into scrape_results table rows
(summary_results + full_profile_results).
"""

from typing import Any, Dict, List, Optional


def transform_fps_response(fps_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    FPS's service.py returns a single flat object:
      { status: "success"|"blocked"|"no_results"|"failed", ...QuickScanProfileData, error? }

    QuickScanProfileData fields (from BaseScraper.ts): name, first_name, last_name,
    age, phones[], emails[], addresses[], relatives[], aliases[], jobs[], education[],
    social_profiles[], detail_link, sources[], scraped_at, ...
    """
    phones = fps_response.get("phones") or []
    addresses = fps_response.get("addresses") or []

    summary = {
        "name": fps_response.get("name"),
        "age": fps_response.get("age"),
        "location": (addresses[0].get("full_address") if addresses else None),
        "phones": [p.get("number") for p in phones if p.get("number")],
        "detail_link": fps_response.get("detail_link"),
    }

    full_profile = {
        k: v for k, v in fps_response.items()
        if k not in ("status", "error")
    }

    return {
        "summary_results": summary,
        "full_profile_results": full_profile if full_profile else None,
    }


def transform_profile_match(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Anywho (via universal-search) returns ProfileMatch objects:
      { id, name, age?, city_state?, phone_snippet?, detail_link?, source,
        match_score?, fullProfile? }
    """
    summary = {
        "id": match.get("id"),
        "name": match.get("name"),
        "age": match.get("age"),
        "location": match.get("city_state"),
        "phone_snippet": match.get("phone_snippet"),
        "detail_link": match.get("detail_link"),
        "source": match.get("source"),
        "match_score": match.get("match_score"),
    }

    full_profile = match.get("fullProfile")

    return {
        "summary_results": summary,
        "full_profile_results": full_profile,
    }


def transform_zaba_service_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    workers/zaba service returns parsed person cards:
      { id, name, age, city_state, phone_snippet, phones[], addresses[],
        relatives[], aliases[], emails[], detail_link, source }
    """
    phones = profile.get("phones") or []
    phone_numbers = []
    for p in phones:
        if isinstance(p, dict) and p.get("number"):
            phone_numbers.append(p["number"])
        elif isinstance(p, str):
            phone_numbers.append(p)

    summary = {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "age": profile.get("age"),
        "location": profile.get("city_state"),
        "phone_snippet": profile.get("phone_snippet") or (phone_numbers[0] if phone_numbers else None),
        "phones": phone_numbers or None,
        "detail_link": profile.get("detail_link"),
        "source": profile.get("source") or "Zabasearch",
    }

    # Full profile is the service card itself (already rich)
    full_profile = {k: v for k, v in profile.items() if k not in ("status", "error")}

    return {
        "summary_results": summary,
        "full_profile_results": full_profile if full_profile else None,
    }


def transform_npd_service_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    workers/npd service returns parsed person cards (same shape as zaba):
      { id, name, age, city_state, phone_snippet, phones[], addresses[],
        relatives[], aliases[], emails[], detail_link, source }
    """
    phones = profile.get("phones") or []
    phone_numbers = []
    for p in phones:
        if isinstance(p, dict) and p.get("number"):
            phone_numbers.append(p["number"])
        elif isinstance(p, str):
            phone_numbers.append(p)

    summary = {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "age": profile.get("age"),
        "location": profile.get("city_state"),
        "phone_snippet": profile.get("phone_snippet") or (phone_numbers[0] if phone_numbers else None),
        "phones": phone_numbers or None,
        "detail_link": profile.get("detail_link"),
        "source": profile.get("source") or "NPD",
    }
    full_profile = {k: v for k, v in profile.items() if k not in ("status", "error")}
    return {
        "summary_results": summary,
        "full_profile_results": full_profile if full_profile else None,
    }


def normalize_fps_row(
    scrape_id: str,
    mode: str,
    scrape_type: str,
    input_data: Dict[str, Any],
    fps_response: Dict[str, Any],
    response_time_ms: int,
    response_bytes: int,
) -> Dict[str, Any]:
    """Build the single DB row for an FPS scrape."""
    status_map = {
        "success": "success",
        "no_results": "success",
        "blocked": "blocked",
        "failed": "failed",
    }
    raw_status = fps_response.get("status", "failed")
    status = status_map.get(raw_status, "failed")

    transformed = transform_fps_response(fps_response) if raw_status == "success" else {
        "summary_results": None,
        "full_profile_results": None,
    }

    return {
        "scrape_id": scrape_id,
        "target": "fps",
        "mode": mode,
        "scrape_type": scrape_type,
        "input_data": input_data,
        "summary_results": transformed["summary_results"],
        "full_profile_results": transformed["full_profile_results"],
        "errors": fps_response.get("error"),
        "status": status,
        "response_time_ms": response_time_ms,
        "response_bytes": response_bytes,
    }


def normalize_zaba_service_rows(
    scrape_id: str,
    mode: str,
    scrape_type: str,
    input_data: Dict[str, Any],
    zaba_response: Dict[str, Any],
    response_time_ms: int,
    response_bytes: int,
) -> List[Dict[str, Any]]:
    """Build DB row(s) from workers/zaba /v1/zaba/search response."""
    raw_status = zaba_response.get("status", "failed")
    profiles = zaba_response.get("profiles") or []

    if raw_status == "failed" or (raw_status != "success" and raw_status != "no_results" and not profiles):
        return [{
            "scrape_id": scrape_id,
            "target": "zabasearch",
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": None,
            "full_profile_results": None,
            "errors": zaba_response.get("error") or raw_status,
            "status": "failed",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        }]

    if not profiles:
        return [{
            "scrape_id": scrape_id,
            "target": "zabasearch",
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": None,
            "full_profile_results": None,
            "errors": None,
            "status": "success",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        }]

    rows = []
    for profile in profiles:
        if scrape_type == "summary":
            transformed = transform_zaba_service_profile(profile)
            rows.append({
                "scrape_id": scrape_id,
                "target": "zabasearch",
                "mode": mode,
                "scrape_type": scrape_type,
                "input_data": input_data,
                "summary_results": transformed["summary_results"],
                "full_profile_results": None,
                "errors": None,
                "status": "success",
                "response_time_ms": response_time_ms,
                "response_bytes": response_bytes,
            })
        elif scrape_type == "full":
            transformed = transform_zaba_service_profile(profile)
            rows.append({
                "scrape_id": scrape_id,
                "target": "zabasearch",
                "mode": mode,
                "scrape_type": scrape_type,
                "input_data": input_data,
                "summary_results": None,
                "full_profile_results": transformed["full_profile_results"],
                "errors": None,
                "status": "success",
                "response_time_ms": response_time_ms,
                "response_bytes": response_bytes,
            })
        else:  # both
            transformed = transform_zaba_service_profile(profile)
            rows.append({
                "scrape_id": scrape_id,
                "target": "zabasearch",
                "mode": mode,
                "scrape_type": scrape_type,
                "input_data": input_data,
                "summary_results": transformed["summary_results"],
                "full_profile_results": transformed["full_profile_results"],
                "errors": None,
                "status": "success",
                "response_time_ms": response_time_ms,
                "response_bytes": response_bytes,
            })
    return rows


def normalize_npd_service_rows(
    scrape_id: str,
    mode: str,
    scrape_type: str,
    input_data: Dict[str, Any],
    npd_response: Dict[str, Any],
    response_time_ms: int,
    response_bytes: int,
) -> List[Dict[str, Any]]:
    """Build DB row(s) from workers/npd /v1/npd/search response."""
    raw_status = npd_response.get("status", "failed")
    profiles = npd_response.get("profiles") or []

    if raw_status == "failed" or (raw_status not in ("success", "no_results") and not profiles):
        return [{
            "scrape_id": scrape_id,
            "target": "npd",
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": None,
            "full_profile_results": None,
            "errors": npd_response.get("error") or raw_status,
            "status": "failed",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        }]

    if not profiles:
        return [{
            "scrape_id": scrape_id,
            "target": "npd",
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": None,
            "full_profile_results": None,
            "errors": None,
            "status": "success",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        }]

    rows = []
    for profile in profiles:
        transformed = transform_npd_service_profile(profile)
        rows.append({
            "scrape_id": scrape_id,
            "target": "npd",
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": transformed["summary_results"] if scrape_type in ("summary", "both") else None,
            "full_profile_results": transformed["full_profile_results"] if scrape_type in ("full", "both") else None,
            "errors": None,
            "status": "success",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        })
    return rows


def normalize_relay_rows(
    scrape_id: str,
    target: str,
    mode: str,
    scrape_type: str,
    input_data: Dict[str, Any],
    universal_search_response: Dict[str, Any],
    response_time_ms: int,
    response_bytes: int,
) -> List[Dict[str, Any]]:
    """
    Build one DB row per match returned by universal-search (AnyWho).
    """

    profiles = universal_search_response.get("profiles") or []
    scraper_failed = universal_search_response.get("scraper_failed", False)

    if not profiles:
        return [{
            "scrape_id": scrape_id,
            "target": target,
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": None,
            "full_profile_results": None,
            "errors": "scraper_failed" if scraper_failed else "no_results",
            "status": "failed" if scraper_failed else "success",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        }]

    rows = []
    for match in profiles:
        transformed = transform_profile_match(match)
        rows.append({
            "scrape_id": scrape_id,
            "target": target,
            "mode": mode,
            "scrape_type": scrape_type,
            "input_data": input_data,
            "summary_results": transformed["summary_results"],
            "full_profile_results": transformed["full_profile_results"],
            "errors": None,
            "status": "success",
            "response_time_ms": response_time_ms,
            "response_bytes": response_bytes,
        })
    return rows
