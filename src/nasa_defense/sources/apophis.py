from __future__ import annotations

from .. import config
from ..models import CloseApproach
from .close_approaches import parse
from .http import get_json


def fetch_approach() -> CloseApproach | None:
    """The 2029 Apophis flyby parameters, via a designation-scoped CAD query
    (the pass is years outside the daily look-ahead window). Returns None on any
    failure — the anchor still shows the countdown."""
    params = {
        "des": config.APOPHIS_DESIGNATION,
        "date-min": "2029-01-01",
        "date-max": "2029-12-31",
    }
    try:
        approaches = parse(get_json(config.CAD_API, params=params))
    except Exception:  # pylint: disable=broad-exception-caught
        return None
    if not approaches:
        return None
    return min(approaches, key=lambda a: a.dist_ld)
