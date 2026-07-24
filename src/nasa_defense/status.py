"""Observatory status contract (schema 1) for this site.

Emits the small, stable status.json the NASA Observatory reads from every
fleet site's root. The contract is specified in the nasa-observatory
repo: docs/superpowers/specs/2026-07-22-nasa-observatory-design.md

Display strings are decided HERE — the Observatory renders them verbatim.
Bounds: headline <= 120 chars, <= 5 items, item text <= 140 chars.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from . import state
from .models import parse_cad_datetime
from .site import _estimate_size_from_h

_SITE_URL = "https://ryastra.github.io/nasa-defense/"
_SBDB = "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr="
_SOURCE_FILES = ("sentry.json", "close_approaches.json", "fireballs.json")


def _number(value: object, fallback: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return float(value) if math.isfinite(value) else fallback


def _streak(value: object) -> int | None:
    number = _number(value, -1)
    return int(number) if number >= 0 and number.is_integer() else None


def _noteworthy(fields: dict) -> bool:
    values = (fields.get(key) for key in ("ts_max", "ps_cum", "ip", "diameter_km"))
    valid = all(value is None or math.isfinite(_number(value, math.nan)) for value in values)
    return valid and fields.get("noteworthy") is True


def _upcoming(cad: dict) -> list[tuple[datetime, str, dict]]:
    """Future close approaches, soonest first, as (timestamp, designation, fields)."""
    now = datetime.now(UTC)
    rows = []
    for key, fields in cad.items():
        des, _, cd = key.partition(":")  # cd itself contains colons; split on the first
        when = parse_cad_datetime(cd)
        if when is None:
            continue
        has_time = ":" in cd
        if has_time and when < now:
            continue
        if not has_time and when.date() < now.date():
            continue
        rows.append((when, des, fields))
    rows.sort(key=lambda row: (row[0], _number(row[2].get("dist_ld"), math.inf)))
    return rows


def _item(when: datetime, des: str, fields: dict) -> dict:
    severity = fields.get("severity", "info")
    distance = _number(fields.get("dist_ld"))
    speed = _number(fields.get("v_rel_kms"))
    text = f"{des} — {distance:.2f} LD, {_estimate_size_from_h(fields.get('h'))}, {speed:.1f} km/s"
    if severity != "info":
        text += f" ({severity})"
    return {"when_utc": when.date().isoformat(), "text": text[:140], "url": _SBDB + quote(des)}


def _watch_timestamp(meta: dict) -> str:
    """Return the watch-run timestamp, rather than the time this file was regenerated."""
    value = meta.get("last_run_utc")
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return "1970-01-01T00:00:00Z"


def build(state_dir: Path) -> dict:
    """The status.json document, built from the committed watcher state."""
    cad = state.load(state_dir / "close_approaches.json")
    sentry = state.load(state_dir / "sentry.json")
    meta = state.load(state_dir / "meta.json")

    upcoming = _upcoming(cad)
    if upcoming:
        when, des, fields = upcoming[0]
        distance = _number(fields.get("dist_ld"))
        headline = f"Next close approach: {des} — {when:%b} {when.day} ({distance:.2f} LD)"
    else:
        headline = "No upcoming close approaches on file"

    noteworthy = sum(1 for fields in sentry.values() if _noteworthy(fields))
    failures = meta.get("consecutive_failures")
    sources_present = all((state_dir / filename).is_file() for filename in _SOURCE_FILES)
    health_known = isinstance(failures, dict) and all(
        filename in failures and _streak(failures[filename]) is not None
        for filename in _SOURCE_FILES
    )
    healthy = health_known and all(_streak(failures[filename]) == 0 for filename in _SOURCE_FILES)
    return {
        "schema": 1,
        "project": "nasa-defense",
        "title": "Planetary-Defense Watch",
        "site": _SITE_URL,
        "updated_utc": _watch_timestamp(meta),
        "fresh_for_hours": 36,
        "ok": bool(meta.get("last_run_utc")) and sources_present and healthy,
        "headline": headline[:120],
        "metrics": [
            {"label": "Sentry noteworthy", "value": str(noteworthy)},
            {"label": "Upcoming approaches", "value": str(len(upcoming))},
        ],
        "items": [_item(*row) for row in upcoming[:5]],
    }
