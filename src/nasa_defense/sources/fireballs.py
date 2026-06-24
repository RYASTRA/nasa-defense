from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .. import config
from ..models import Fireball
from .http import get_json


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _signed(row: list, idx: dict, mag_field: str, dir_field: str, negative: str) -> float | None:
    if mag_field not in idx:
        return None
    magnitude = _to_float(row[idx[mag_field]])
    if magnitude is None:
        return None
    direction = row[idx[dir_field]] if dir_field in idx else None
    return -magnitude if direction == negative else magnitude


def parse(raw: dict) -> list[Fireball]:
    fields = raw.get("fields") or []
    idx = {name: i for i, name in enumerate(fields)}
    fireballs: list[Fireball] = []
    for row in raw.get("data", []):
        when = row[idx["date"]] if "date" in idx else None
        impact_e = _to_float(row[idx["impact-e"]]) if "impact-e" in idx else None
        if not when or impact_e is None:
            continue
        fireballs.append(
            Fireball(
                date=when,
                impact_e_kt=impact_e,
                energy=_to_float(row[idx["energy"]]) if "energy" in idx else None,
                lat=_signed(row, idx, "lat", "lat-dir", "S"),
                lon=_signed(row, idx, "lon", "lon-dir", "W"),
            )
        )
    return fireballs


def fetch(today: date | None = None) -> list[Fireball]:
    today = today or date.today()
    params = {"date-min": (today - timedelta(days=config.FETCH_LOOKBACK_DAYS)).isoformat()}
    return parse(get_json(config.FIREBALL_API, params=params))
