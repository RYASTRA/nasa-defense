"""CNEOS CAD close-approach data: fetch and parse into CloseApproach records."""

from __future__ import annotations

from datetime import date, timedelta

from .. import config
from ..models import CloseApproach
from .http import get_json
from .parsing import finite_float


def parse(raw: dict) -> list[CloseApproach]:
    """Convert a raw CAD payload into CloseApproach records.

    CAD returns column-oriented data — a `fields` list naming the columns and `data` rows
    positioned against it — so columns are resolved by name, and rows missing a designation,
    date, or distance are skipped.
    """
    fields = raw.get("fields") or []
    idx = {name: i for i, name in enumerate(fields)}
    approaches: list[CloseApproach] = []
    for row in raw.get("data", []):
        des = row[idx["des"]] if "des" in idx else None
        cd = row[idx["cd"]] if "cd" in idx else None
        dist_au = finite_float(row[idx["dist"]]) if "dist" in idx else None
        if not des or not cd or dist_au is None:
            continue
        v_rel = finite_float(row[idx["v_rel"]]) if "v_rel" in idx else None
        approaches.append(
            CloseApproach(
                des=des,
                cd=cd,
                dist_au=dist_au,
                dist_ld=dist_au / config.AU_PER_LUNAR_DISTANCE,
                v_rel_kms=v_rel or 0.0,
                h=finite_float(row[idx["h"]]) if "h" in idx else None,
            )
        )
    return approaches


def fetch(today: date | None = None) -> list[CloseApproach]:
    """Fetch approaches inside the configured look-back, look-ahead, and distance window."""
    today = today or date.today()
    params = {
        "date-min": (today - timedelta(days=config.FETCH_LOOKBACK_DAYS)).isoformat(),
        "date-max": (today + timedelta(days=config.CAD_LOOKAHEAD_DAYS)).isoformat(),
        "dist-max": f"{config.CAD_MAX_LUNAR_DISTANCES}LD",
    }
    return parse(get_json(config.CAD_API, params=params))
