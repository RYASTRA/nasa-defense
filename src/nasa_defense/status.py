"""Observatory status contract (schema 1) for this site.

Emits the small, stable status.json the NASA Observatory reads from every
fleet site's root. Contract spec:
https://github.com/RYASTRA/nasa-observatory/blob/main/docs/superpowers/specs/2026-07-22-nasa-observatory-design.md

Display strings are decided HERE — the Observatory renders them verbatim.
Bounds: headline <= 120 chars, <= 5 items, item text <= 140 chars.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

from . import state
from .models import parse_cad_date
from .site import _estimate_size_from_h

_SITE_URL = "https://ryastra.github.io/nasa-defense/"
_SBDB = "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr="


def _upcoming(cad: dict) -> list[tuple[date, str, dict]]:
    """Future close approaches, soonest first, as (date, designation, fields)."""
    today = date.today()
    rows = []
    for key, fields in cad.items():
        des, _, cd = key.partition(":")  # cd itself contains colons; split on the first
        when = parse_cad_date(cd)
        if when is None or when < today:
            continue
        rows.append((when, des, fields))
    rows.sort(key=lambda row: row[0])
    return rows


def _item(when: date, des: str, fields: dict) -> dict:
    severity = fields.get("severity", "info")
    text = (
        f"{des} — {fields.get('dist_ld', 0.0):.2f} LD, "
        f"{_estimate_size_from_h(fields.get('h'))}, "
        f"{fields.get('v_rel_kms', 0.0):.1f} km/s"
    )
    if severity != "info":
        text += f" ({severity})"
    return {"when_utc": when.isoformat(), "text": text[:140], "url": _SBDB + quote(des)}


def build(state_dir: Path) -> dict:
    """The status.json document, built from the committed watcher state."""
    cad = state.load(state_dir / "close_approaches.json")
    sentry = state.load(state_dir / "sentry.json")
    meta = state.load(state_dir / "meta.json")

    upcoming = _upcoming(cad)
    if upcoming:
        when, des, fields = upcoming[0]
        headline = (
            f"Next close approach: {des} — {when:%b %-d} ({fields.get('dist_ld', 0.0):.2f} LD)"
        )
    else:
        headline = "No upcoming close approaches on file"

    noteworthy = sum(1 for d in sentry.values() if d.get("noteworthy"))
    failures = meta.get("consecutive_failures", {})
    return {
        "schema": 1,
        "project": "nasa-defense",
        "title": "Planetary-Defense Watch",
        "site": _SITE_URL,
        "updated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fresh_for_hours": 36,
        "ok": all(v == 0 for v in failures.values()),
        "headline": headline[:120],
        "metrics": [
            {"label": "Sentry noteworthy", "value": str(noteworthy)},
            {"label": "Upcoming approaches", "value": str(len(upcoming))},
        ],
        "items": [_item(*row) for row in upcoming[:5]],
    }
