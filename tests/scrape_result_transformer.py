"""
Result Transformer — Convert real scraper responses to DB schema format
==========================================================================

Each scraper's real response shape is different:
  - FPS (service.py):        single object, QuickScanProfileData shape
  - Anywho/Zabasearch
    (universal-search):      { profiles: ProfileMatch[] }, one row per match

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
    Anywho/Zabasearch (via universal-search) return ProfileMatch objects:
      { id, name, age?, city_state?, phone_snippet?, detail_link?, source,
        match_score?, fullProfile? }

    fullProfile (when present, e.g. Zabasearch) is a legacy PersonProfile shape.
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
    Build one DB row per match returned by universal-search for
    Anywho/Zabasearch. Returns an empty list if the call failed outright
    (caller should log a single failed row in that case).
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
