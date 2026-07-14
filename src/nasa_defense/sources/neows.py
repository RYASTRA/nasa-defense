from __future__ import annotations

import re
import sys
from datetime import date, timedelta

from .. import config
from .http import get_json

_NEOWS_FEED_MAX_DAYS = 7  # NeoWs /feed accepts at most a 7-day span


def _designation_keys(neo: dict) -> set[str]:
    """Designation strings a NeoWs object might be matched on (number and/or
    provisional designation), to maximise joins against Sentry/CAD `des`."""
    keys: set[str] = set()
    des = neo.get("designation")
    if des:
        keys.add(str(des).strip())
    name = (neo.get("name") or "").strip()
    if name:
        number = re.match(r"^\s*(\d+)\b", name)
        if number:
            keys.add(number.group(1))
        paren = re.search(r"\(([^)]+)\)", name)
        if paren:
            keys.add(paren.group(1).strip())
    return {k for k in keys if k}


def fetch_pha_lookup(today: date | None = None) -> dict[str, dict]:
    """Best-effort enrichment: {designation: {"pha": bool, "diameter_m": float|None}}.
    Returns {} on any failure (NeoWs is non-critical; the run proceeds without it)."""
    today = today or date.today()
    lookback = min(config.FETCH_LOOKBACK_DAYS, _NEOWS_FEED_MAX_DAYS)
    params = {
        "start_date": (today - timedelta(days=lookback)).isoformat(),
        "end_date": today.isoformat(),
        "api_key": config.nasa_api_key(),
    }
    try:
        raw = get_json(config.NEOWS_FEED, params=params)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Non-critical, but say so: silently returning {} strips the PHA flag and the
        # diameter off every issue this run, with nothing anywhere to explain why.
        print(f"neows enrichment unavailable: {exc}", file=sys.stderr)
        return {}

    lookup: dict[str, dict] = {}
    for day_objects in (raw.get("near_earth_objects") or {}).values():
        for neo in day_objects:
            meters = (neo.get("estimated_diameter") or {}).get("meters") or {}
            dmin = meters.get("estimated_diameter_min")
            dmax = meters.get("estimated_diameter_max")
            entry = {
                "pha": bool(neo.get("is_potentially_hazardous_asteroid")),
                "diameter_m": (dmin + dmax) / 2 if dmin is not None and dmax is not None else None,
            }
            for key in _designation_keys(neo):
                lookup[key] = entry
    return lookup
